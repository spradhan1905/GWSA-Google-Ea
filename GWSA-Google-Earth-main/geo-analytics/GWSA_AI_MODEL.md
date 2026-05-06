# GWSA GeoAnalytics AI Model

This document reviews the current AI/chat implementation and defines the target model for a stronger GWSA GeoAnalytics assistant. The goal is to move from a small heuristic chat wrapper to a grounded analytics orchestration layer that lets users type natural business questions about sales, revenue, door count, net income, operating expenses, expense ratio, trends, rankings, comparisons, and store performance while still answering only from approved SQL data.

## Current State

The current AI flow is implemented mainly in:

- `backend/routes/chat.py`
- `backend/db/queries.py`
- `frontend/src/hooks/useGeminiChat.js`
- `frontend/src/components/Chat/ChatMessage.jsx`

Current request flow:

```text
User message
  -> frontend useGeminiChat
  -> POST /api/chat
  -> chat.py heuristic planner
  -> approved helper in db/queries.py
  -> Azure OpenAI or Gemini fallback
  -> reply + sql_used/data
  -> ChatMessage renders answer and Data Action
```

What is already good:

- The browser never receives AI provider keys.
- SQL values are parameterized in `db/queries.py`.
- Table/object names are pulled from config and validated before interpolation.
- AI-generated SQL is effectively disabled in `try_text_to_sql()`, which is safer than free-form SQL generation.
- The chat route only executes approved analytics actions: `location_summary`, `compare_locations`, and `rank_locations`.
- The assistant can pass structured analytics data into the model instead of asking the model to guess.

Current limitations:

- Intent coverage is too narrow. The planner only knows location summary, comparison, and ranking.
- Metric coverage is too narrow. It only detects `revenue` and `door_count`.
- Granularity is not modeled. The assistant does not explicitly distinguish daily, monthly, MTD, YTD, trailing-period, location-level, and organization-level questions.
- Source selection is implicit. `TotalCoreTableFinal`, `RetailStoreMonthlyFinancialSummary`, and `PeopleCounter.dbo.PCounter` are chosen inside helper functions, but the AI layer does not expose why a source was used.
- Unsupported requests are not classified before answering. For example, a user asking "which day and date had the highest sale value from all retail stores in March" needs a daily all-store revenue action. If that action is unavailable, the assistant should say exactly that instead of answering with a location-level monthly total.
- The prompt is too general. It says to use structured data faithfully, but it does not enforce a strict evidence contract, citation style, or "do not answer beyond retrieved data" behavior.
- Conversation memory is only recent frontend messages. There is no structured session state for selected location, last timeframe, last metric, resolved store aliases, or previous data actions.
- The frontend only displays `sql_used` as "Data Action"; it does not yet show sources, confidence, follow-up questions, chart payloads, or data gaps.

## Target Architecture

```text
User query
  -> Session memory
  -> Query planner
  -> Entity + timeframe + metric parser
  -> Source router
  -> Approved analytics retrieval
  -> Context assembler
  -> LLM answer composer
  -> Response contract
  -> Frontend answer, source cards, follow-ups, chart data
  -> Persistent/session memory
```

GWSA-specific version:

```text
User query
  "For March, which day had the highest sales value from all retail stores?"

Session memory
  selected location, recent questions, last metric/timeframe, current dashboard date range

Query planner
  intent: rank_time_periods
  metric: revenue
  grain: day
  scope: all retail stores
  timeframe: 2026-03-01 to 2026-03-31

Source router
  revenue daily current/custom period -> TotalCoreTableFinal when dates are available
  revenue monthly historical period -> RetailStoreMonthlyFinancialSummary
  door count daily -> PeopleCounter.dbo.PCounter
  trends -> combined financial + door-count rollup
  donor geography -> DonorAddresses/KML layers

Approved analytics retrieval
  run parameterized helper only

Context assembler
  normalize rows, calculate leader/rank/change, attach source metadata, trim payload

LLM answer composer
  answer only from retrieved evidence
  cite data action/source
  state missing data explicitly

Response
  text, data_action, sources, followups, chart, data_gap, confidence
```

## Core Design Principles

1. Users should be able to ask normal business questions.

The chat experience should support broad natural language questions such as:

- "Which store had the highest sales in March?"
- "What was our door count last week?"
- "Compare revenue and net income for DeZavala and Blanco."
- "Which stores have the highest operating expenses?"
- "What is the expense ratio trend for Bandera?"
- "Did revenue go up while door count went down?"
- "Show stores with high sales but low net income."
- "What changed from February to March?"

The backend should translate those questions into typed plans, not expect users to know table names, metric names, or exact dashboard terminology.

2. The LLM should not decide what SQL to run.

The LLM can help phrase a response, but the backend should decide the allowed action and call approved helpers. This keeps the system safe and more predictable.

3. The planner must produce a typed query plan.

Instead of only `action`, `metric`, `store_names`, `limit`, and `timeframe`, the plan should include:

```json
{
  "intent": "rank_time_periods",
  "metric": "revenue",
  "grain": "day",
  "scope": "all_retail_stores",
  "locations": [],
  "location_type": "store",
  "timeframe": {
    "start": "2026-03-01",
    "end": "2026-03-31",
    "label": "March 2026"
  },
  "limit": 1,
  "requires_chart": false
}
```

4. Every answer must be tied to a retrieved data payload.

If no approved action can retrieve the needed data, the assistant should return a data-gap response:

```text
I cannot answer that from the currently available action set because this asks for daily all-store revenue by date. I have monthly/location revenue and daily selected-store revenue helpers, but no approved daily all-retail-store ranking helper yet.
```

5. Data grain must be explicit.

The system must know whether the user is asking about:

- Daily values
- Monthly values
- Current month to date
- Year to date
- Last 30 days
- Last completed N months
- Store-level data
- All-store totals
- Retail stores only
- Donation stations only
- Consolidated organization totals

6. The response should carry structured metadata, not just prose.

The frontend should eventually receive:

```json
{
  "reply": "...",
  "data_action": "rank_periods:revenue:day",
  "data": {},
  "sources": [
    {
      "name": "JS_API.dbo.TotalCoreTableFinal",
      "grain": "daily",
      "metric": "Revenue",
      "date_range": "2026-03-01 to 2026-03-31"
    }
  ],
  "followups": [
    "Show the top 5 sales days in March",
    "Break that day down by store",
    "Compare March daily sales to door count"
  ],
  "chart": {
    "type": "bar",
    "x": "date",
    "y": "revenue",
    "rows": []
  },
  "data_gap": null,
  "confidence": "high"
}
```

## Recommended Backend Modules

The current `chat.py` is doing too many jobs. Split it into smaller AI modules:

```text
backend/ai/
  __init__.py
  prompts.py
  planner.py
  schemas.py
  router.py
  context.py
  composer.py
  memory.py
  responses.py

backend/db/
  queries.py
  analytics_actions.py
```

Recommended responsibilities:

- `planner.py`: Parse user query into a typed `AnalyticsPlan`.
- `schemas.py`: Define allowed intents, metrics, grains, scopes, and response models.
- `router.py`: Map plan to an approved backend action.
- `context.py`: Normalize rows, compute summaries/rankings, attach source metadata.
- `composer.py`: Build LLM messages with a strict grounded-answer prompt.
- `memory.py`: Track selected location, recent timeframe, metric, and previous action.
- `responses.py`: Standardize success, data gap, provider error, and validation error responses.
- `analytics_actions.py`: House approved analytics functions that are safe for chat use.

## Recommended Intent Catalog

Initial supported intents should be:

| Intent | Example | Required helper |
| --- | --- | --- |
| `location_summary` | "How is DeZavala doing this month?" | existing |
| `compare_locations` | "Compare DeZavala vs Blanco for March" | existing |
| `rank_locations` | "Top 5 stores by revenue in March" | existing |
| `rank_time_periods` | "Which day in March had the highest sales?" | new |
| `trend_summary` | "Show revenue trend for the last 12 months" | existing `get_trends`, needs chat wrapper |
| `metric_breakdown` | "Break March revenue down by store" | new or extend ranking |
| `multi_metric_summary` | "Sales, door count, net income, and expenses for March" | new |
| `compare_periods` | "How did March compare to February?" | new |
| `correlation_check` | "Did door count track revenue in March?" | new combined action |
| `derived_metric` | "Revenue per visitor for each store" | new |
| `data_catalog` | "What data can I ask about?" | new metadata-only action |
| `map_context_summary` | "What do donor addresses show for this location?" | future |
| `unsupported` | "Who managed the store?" or unavailable grain | no DB call |

## Recommended Metrics

Start with a controlled metric catalog. Users should be able to ask for these metrics using common synonyms.

| Canonical metric | User may say | Source | Grain | Notes |
| --- | --- | --- | --- | --- |
| `sales` | sales, sale value, core sales, sold amount | `TotalCoreTableFinal` or monthly summary | daily/monthly | Treat as `revenue` unless a separate POS sales metric is added |
| `revenue` | revenue, total revenue, net revenue, income from sales | `TotalCoreTableFinal` or `RetailStoreMonthlyFinancialSummary` | daily/monthly | Daily source for date-level questions; monthly source for financial rollups |
| `net_income` | net income, profit, bottom line | `RetailStoreMonthlyFinancialSummary` | monthly | Financial summary metric |
| `operating_expenses` | expenses, operating expenses, total operating expenses | `RetailStoreMonthlyFinancialSummary` | monthly | Include personnel expenses separately if requested |
| `personnel_expenses` | payroll, labor, personnel expense, staffing expense | `RetailStoreMonthlyFinancialSummary` | monthly | Already present in monthly select columns |
| `expense_ratio` | expense ratio, cost ratio, expense percent | `RetailStoreMonthlyFinancialSummary` | monthly | Derived in financial helpers |
| `door_count` | door count, visits, visitors, traffic, donor visits | `PeopleCounter.dbo.PCounter` | daily | Sums configured `[In]` column |
| `avg_daily_door_count` | average visits, average daily traffic | derived from door count | period | Derived metric |
| `revenue_per_visit` | revenue per visitor, sales per visit, conversion | revenue + door count | daily/monthly | Future derived metric |
| `change` | change, increase, decrease, growth, dropped, up/down | derived from selected metric | period-over-period | Needs baseline and comparison period |

Metric parser rules:

- Map "sales" and "sale value" to `revenue` unless a distinct POS sales metric is intentionally added.
- Keep `revenue`, `net_income`, and `operating_expenses` separate. They answer different financial questions.
- When the user says "performance", infer a multi-metric summary: revenue, net income, operating expenses, expense ratio, and door count when available.
- When the user says "traffic", infer `door_count`.
- When the user asks "why", answer only with observed metric changes unless external cause data exists.

## Natural Language Coverage

The assistant should support flexible question shapes, not just exact phrases.

| Question shape | Examples | Plan pattern |
| --- | --- | --- |
| Ranking locations | "Top stores by sales", "highest operating expenses", "lowest net income" | `rank_locations` |
| Ranking dates | "Which day had the highest sales?", "busiest date in March" | `rank_time_periods` |
| Comparing stores | "Compare Blanco and DeZavala revenue" | `compare_locations` |
| Comparing periods | "March vs February sales", "this month compared to last month" | `compare_periods` |
| Summarizing one store | "How is Bandera doing?" | `location_summary` |
| Trends | "Show 12 month net income trend" | `trend_summary` |
| Breakdowns | "Break March sales down by store" | `metric_breakdown` |
| Multi-metric questions | "Sales, door count, and net income for March" | `multi_metric_summary` |
| Derived metrics | "Revenue per visitor" | `derived_metric` |
| Data availability | "What data can I ask about?" | `data_catalog` |

The plan should allow more than one metric:

```json
{
  "intent": "multi_metric_summary",
  "metrics": ["revenue", "door_count", "net_income", "operating_expenses"],
  "grain": "month",
  "scope": "location",
  "locations": ["DeZavala Retail Store"],
  "timeframe": {
    "start": "2026-03-01",
    "end": "2026-03-31",
    "label": "March 2026"
  }
}
```

## Needed Query Helpers

Add approved helpers for common questions the current assistant cannot answer reliably.

### 1. Daily Revenue Ranking

Purpose:

Answer questions like:

```text
For March, which day/date had the highest sales value from all retail stores?
```

Suggested function:

```python
def rank_revenue_days(start_date: str, end_date: str, scope: str = "all_retail_stores", limit: int = 1) -> dict:
    ...
```

Expected result:

```json
{
  "metric": "revenue",
  "grain": "day",
  "scope": "all_retail_stores",
  "timeframe": {
    "start": "2026-03-01",
    "end": "2026-03-31"
  },
  "periods": [
    {
      "date": "2026-03-14",
      "metric_value": 123456.78
    }
  ],
  "source": {
    "name": "JS_API.dbo.TotalCoreTableFinal",
    "grain": "daily",
    "filters": ["Category/RevenueType = Core Sales", "retail stores only"]
  }
}
```

### 2. Store Breakdown for a Day or Month

Suggested function:

```python
def rank_store_revenue(start_date: str, end_date: str, limit: int = 10, location_type: str = "store") -> dict:
    ...
```

This can support:

- "Which store had the highest revenue in March?"
- "Break the top sales day down by store."
- "Top 10 retail stores by revenue this month."

### 3. Daily Door Count Ranking

Suggested function:

```python
def rank_door_count_days(start_date: str, end_date: str, scope: str = "all_locations", limit: int = 1) -> dict:
    ...
```

This can support:

- "Which day had the highest door count in March?"
- "What was the busiest date last month?"

### 4. Combined Revenue and Door Count

Suggested function:

```python
def get_revenue_door_count_series(store_id: str, start_date: str, end_date: str, grain: str = "day") -> dict:
    ...
```

This can support:

- "Did more visitors mean more revenue?"
- "Show revenue per visitor for March."
- "Which stores had high traffic but low revenue?"

## Prompt Contract

Replace the current broad `SYSTEM_CONTEXT` with a stricter answer contract.

Recommended system prompt:

```text
You are the GWSA GeoAnalytics assistant for Goodwill Industries of San Antonio.

Rules:
1. Answer only from the structured analytics data provided in the current request.
2. Do not invent missing dates, stores, metrics, managers, causes, or comparisons.
3. If the data does not answer the user's exact question, say what is missing and what available data can answer.
4. Keep answers concise and operationally useful.
5. Use exact metric names, date ranges, and store names from the data payload.
6. Never expose raw SQL credentials, connection details, or hidden configuration.
7. Do not mention individual manager names; refer only to roles.
8. When ranking, name the winner, value, timeframe, and source grain.
9. When useful, suggest 2-3 follow-up questions based on available actions.
```

Recommended user prompt format:

```text
Current dashboard context:
{store_context}

Conversation memory:
{memory_summary}

Approved analytics action:
{data_action}

Retrieved evidence:
{json_payload}

Data gaps:
{data_gap}

User question:
{user_message}
```

## Response Types

The API should distinguish these response types:

| Type | When | HTTP |
| --- | --- | --- |
| `answer` | Retrieved data answers the question | 200 |
| `partial_answer` | Data answers part of the question | 200 |
| `data_gap` | No approved action/source supports the request | 200 |
| `clarification_needed` | Required entity/timeframe is ambiguous | 200 |
| `provider_error` | LLM failed after data retrieval | 429/502/504/500 |
| `validation_error` | Bad request payload | 400 |

Important: a `data_gap` is not a failure. It is a correct grounded response when the project does not yet have the requested data/action.

## Immediate Fix Priority

1. Add `grain`, `scope`, and `intent` to the chat plan.
2. Add data-gap detection before calling the LLM.
3. Add daily all-store revenue ranking for questions about highest sales day/date.
4. Add source metadata to every approved action response.
5. Strengthen the system prompt to require grounded answers only.
6. Rename frontend `sqlUsed` display to `Data Action` everywhere internally, since no raw SQL should be exposed.
7. Add chat tests for common business questions.

## Example: Correct Handling of the March Daily Sales Question

User:

```text
For the month of March, which day and date had the highest sale value from all retail stores?
```

Planner should produce:

```json
{
  "intent": "rank_time_periods",
  "metric": "revenue",
  "grain": "day",
  "scope": "all_retail_stores",
  "timeframe": {
    "start": "2026-03-01",
    "end": "2026-03-31",
    "label": "March 2026"
  },
  "limit": 1
}
```

If `rank_revenue_days()` exists and returns rows:

```text
The highest all-retail-store sales day in March 2026 was Friday, March 14, 2026, with $123,456.78 in Core Sales revenue.

Source: JS_API.dbo.TotalCoreTableFinal, daily revenue, March 1-31, 2026.
```

If the helper does not exist yet:

```text
I cannot answer that exact question yet because it requires daily all-retail-store revenue ranking. The current chat actions can rank stores by revenue and summarize selected locations, but they do not yet rank dates across all retail stores.
```

## Test Questions

Use these as acceptance tests for the improved model:

- "Which store had the highest revenue in March 2026?"
- "For March 2026, which day had the highest sales across all retail stores?"
- "Show the top 5 sales days in March."
- "Compare DeZavala and Blanco Retail Store for March revenue."
- "Which location had the highest door count last 30 days?"
- "For this selected store, what was revenue per visitor in March?"
- "Show the last 12 months of revenue and door count for Bandera."
- "What data do you have for donation stations?"
- "Who is the manager of Blanco?" Expected: no individual manager names.
- "Why did revenue drop?" Expected: only describe observed data unless supporting cause data exists.

## Implementation Notes

- Keep AI-generated SQL disabled unless there is a separate reviewed sandbox with strict read-only permissions, query parser validation, table allowlists, row limits, and query cost controls.
- Prefer deterministic planners and approved actions for recurring executive/operations questions.
- Add model-based planning only after the typed schema and action router exist; the model should return JSON that is validated before execution.
- Keep payloads small. The context assembler should send summary rows and top-K detail, not entire result sets.
- Store source metadata with each action so the assistant can explain whether a number came from daily revenue, monthly financial summaries, or PeopleCounter.
- Add unit tests for planner behavior before expanding the LLM prompt.
