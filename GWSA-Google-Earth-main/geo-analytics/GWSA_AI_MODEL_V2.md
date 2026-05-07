# GWSA GeoAnalytics AI Model V2 — Complete Specification

## Why V2

The V1 AI chat works but has real problems users feel immediately:

1. **Slow responses.** The heuristic planner runs per-store SQL loops sequentially, then waits for a full LLM round-trip. A "top 5 stores" question fires 30+ individual queries before GPT even sees the prompt.
2. **Robotic tone.** The system prompt enforces grounded answers but the output reads like a database report, not a conversation. Users compare it to ChatGPT and Claude and it falls short.
3. **Narrow intent coverage.** The planner only recognizes a handful of regex patterns. Anything outside that narrow window gets "unsupported" even when the data exists to answer it.
4. **Memory is a stub.** `memory.py` summarizes recent turns into a string but nothing persists across the session boundary. The assistant forgets what store the user was looking at two messages ago.
5. **Back-calculation bottleneck.** Every answer requires the planner to map to a pre-built query helper. If a helper does not exist, the question is unanswerable, even if the underlying tables have the data.

V2 addresses all five by restructuring the pipeline, upgrading the LLM layer, and expanding what the system can answer.

---

## Target Experience

A user opens the GeoAnalytics map, clicks a store pin, and types:

> "What store had the highest sale per day for the month of February and how much was it?"

The assistant responds in under 4 seconds with something like:

> The strongest single-day revenue in February 2026 came from the Fredericksburg Rd Retail Store on Saturday the 14th, pulling in $18,742.63 in core sales. That was about $3,200 more than the next closest day across the network.
>
> Want me to break down that day by store, or show the top 5 revenue days for February?

That is the bar. Natural, precise, fast, grounded, and offering useful next steps.

---

## Architecture Overview

```
User message
  → Session memory (resolve pronouns, carry forward store/metric/timeframe)
  → LLM-assisted planner (structured output, not regex)
  → Validation gate (reject hallucinated intents, enforce schema)
  → Set-based SQL retrieval (one query per intent, not per-store loops)
  → Evidence assembler (trim, annotate sources, flag gaps)
  → LLM answer composer (conversational, grounded, with follow-ups)
  → Structured response envelope
  → Frontend rendering (answer + sources + chart + follow-up chips)
```

### Key Architectural Changes from V1

| Area | V1 | V2 |
|---|---|---|
| Planner | Regex heuristics in Python | LLM structured output with JSON schema enforcement |
| SQL pattern | Per-store Python loops (N+1) | Set-based SQL with GROUP BY across all stores in one query |
| LLM model | GPT-5.4-mini (single bloated call) | GPT-5.4-mini (two focused calls: planner + composer) |
| Memory | Stub that summarizes last 6 turns as a string | Session state object tracking store, metric, timeframe, last intent, and pending follow-ups |
| System prompt | Generic "be helpful" with rules bolted on | Two-stage prompt: planner prompt (structured) + composer prompt (conversational) |
| Response time target | No target (often 8-15 seconds) | Under 5 seconds for simple questions, under 8 for complex |
| Follow-ups | None | 2-3 context-aware suggestions per response |
| Error handling | Generic "AI unavailable" | Graceful degradation: quota fallback shows raw data, timeout retries once with shorter prompt |

---

## Module Responsibilities

```
backend/ai/
  __init__.py          Package entry point
  schemas.py           Intent catalog, metric vocabulary, plan schema, response models
  planner.py           LLM-assisted intent classification + slot filling
  planner_prompt.py    System prompt and few-shot examples for the planner LLM call
  router.py            Map validated plan → approved SQL retrieval function
  retrieval.py         Set-based SQL query builders (replaces per-store loops)
  context.py           Evidence trimming, source metadata, data-gap detection
  composer.py          Build grounded LLM messages for the answer
  composer_prompt.py   System prompt for the conversational answer composer
  memory.py            Session state: selected store, last metric, last timeframe, pronoun resolution
  responses.py         Standardized JSON response envelopes
  followups.py         Context-aware follow-up suggestion engine

backend/db/
  connection.py        SQL Server connection pool
  queries.py           Low-level parameterized query execution (shared by retrieval.py)
  analytics_actions.py Approved action dispatcher (thin router between plan and retrieval)
```

---

## Session Memory (memory.py)

### What V1 Does

```python
def summarize_history(history: list, max_turns: int = 6) -> str:
    # Joins last 6 messages into a string. No state extraction. No persistence.
```

### What V2 Does

Memory tracks a session state object that accumulates across turns within a single chat session. It does not persist across browser refreshes (that requires a session store, covered in Phase 3).

```python
@dataclass
class SessionState:
    selected_store: Optional[str] = None        # LocationID or name from map click or last mention
    selected_store_name: Optional[str] = None    # Display name for the composer
    last_metric: Optional[str] = None            # "revenue", "door_count", etc.
    last_timeframe: Optional[dict] = None        # {"start": ..., "end": ..., "label": ...}
    last_intent: Optional[str] = None            # "rank_locations", "compare_locations", etc.
    last_data_action: Optional[str] = None       # "rank_locations:revenue", etc.
    last_store_names: list = field(default_factory=list)  # For "compare those two again"
    pending_followups: list = field(default_factory=list)  # Suggested follow-ups from last turn
    turn_count: int = 0
```

#### Pronoun and Reference Resolution

Before the planner sees the user message, memory resolves implicit references:

| User says | Memory resolves to |
|---|---|
| "What about door count?" | metric=door_count, keep last store and timeframe |
| "And for March?" | timeframe=March, keep last store and metric |
| "Compare it with Blanco" | compare selected_store vs Blanco, keep last metric and timeframe |
| "Do that" / "Sure" / "Yes" | Re-run pending_followup[0] if available |
| "This store" / "the selected store" | selected_store from map context |
| "Same thing but for last month" | Shift timeframe, keep everything else |

Implementation: `resolve_references(user_message, session_state, store_context) -> ResolvedQuery` produces an enriched message with explicit values filled in. The planner then works on the resolved query, not raw user text.

#### History Summary for Composer

The composer still gets a text summary of recent turns, but now it is structured:

```python
def build_memory_context(session: SessionState, history: list, max_turns: int = 6) -> str:
    lines = []
    if session.selected_store_name:
        lines.append(f"Active store: {session.selected_store_name}")
    if session.last_metric:
        lines.append(f"Last metric discussed: {session.last_metric}")
    if session.last_timeframe:
        lines.append(f"Last timeframe: {session.last_timeframe.get('label', '')}")
    lines.append("")
    for item in history[-max_turns:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content[:300]}")
    return "\n".join(lines) if lines else "(new conversation)"
```

---

## LLM-Assisted Planner (planner.py)

### Why Replace Regex Heuristics

The V1 planner uses `wants_rank_time_periods()`, `wants_correlation()`, `wants_peak_store_single_day_revenue()`, and dozens of similar regex functions. This is fragile:

- "What store had the highest sale per day for February" fails because the regex expects "which day" not "which store...per day."
- "Show me how Bandera did last quarter" fails because no regex covers "last quarter."
- "Is revenue up or down?" fails if the user does not say "compare" or "vs."
- Any question phrased differently from what the developer anticipated gets "unsupported."

### V2 Planner: LLM Structured Output

The planner makes a fast, cheap LLM call (GPT-5.4-mini with structured output / JSON mode) that classifies the intent and extracts slots in one pass. The call is cheap because the prompt is short (system prompt + user message + session state, no evidence payload).

#### Planner Prompt (planner_prompt.py)

```
You are an intent classifier for a retail analytics dashboard at Goodwill Industries of San Antonio.

Given the user's question and session context, output a JSON plan object. Do not answer the question itself. Only classify and extract slots.

## Available Intents

- location_summary: How is a specific store doing? General performance overview.
- compare_locations: Compare 2 stores on a metric.
- rank_locations: Which stores are highest/lowest for a metric?
- rank_time_periods: Which day/week had the highest/lowest metric value?
- peak_store_daily_revenue: Which specific store had the best single-day revenue?
- trend_summary: Show metric trend over time for a store (monthly).
- metric_breakdown: Break a metric down by store for a time period.
- multi_metric_summary: Multiple metrics for one store in a time period.
- compare_periods: Compare two time periods (e.g. March vs February).
- correlation_check: Do two metrics track together (e.g. door count vs revenue)?
- derived_metric: Computed metric like revenue per visit.
- revenue_door_series: Daily aligned revenue + door count for one store.
- data_catalog: What data/questions are available?
- map_context_summary: Donor geography for a store.
- unsupported: Question cannot be answered from available data (HR, personnel names, external data).

## Available Metrics

- revenue (aliases: sales, sale value, core sales, total revenue, net revenue)
- door_count (aliases: door count, visits, visitors, traffic, donor visits)
- net_income (aliases: net income, profit, bottom line)
- operating_expenses (aliases: expenses, operating expenses, opex)
- personnel_expenses (aliases: payroll, labor, staffing)
- expense_ratio (aliases: cost ratio, expense percent)
- revenue_per_visit (aliases: revenue per visitor, sales per visit, conversion)

## Available Grains

- day: Daily-level data (TotalCoreTableFinal for revenue, PCounter for door count)
- month: Monthly aggregates (RetailStoreMonthlyFinancialSummary)
- period: Aggregated over a date range

## Available Scopes

- location: One specific store
- all_retail_stores: All retail stores and outlets
- all_locations: Everything including donation stations
- consolidated: Network-wide totals

## Output Schema

{
  "intent": string,          // one of the intents above
  "metrics": [string],       // one or more canonical metric names
  "grain": string,           // "day", "month", or "period"
  "scope": string,           // "location", "all_retail_stores", "all_locations", "consolidated"
  "locations": [string],     // store names mentioned (empty if scope is network-wide)
  "timeframe": {             // null if not specified
    "type": string,          // "named_month", "this_month", "last_month", "last_n_days", "ytd", "last_year", "custom", "last_quarter"
    "month_name": string,    // e.g. "February" (for named_month)
    "year": int,             // e.g. 2026
    "n_days": int,           // for last_n_days
    "start": string,         // ISO date if custom
    "end": string            // ISO date if custom
  },
  "timeframe_b": {},         // second timeframe for compare_periods (same schema)
  "limit": int,              // top-K for rankings (default 5)
  "sort_direction": string,  // "desc" (highest first) or "asc" (lowest first)
  "requires_chart": boolean, // true if the answer would benefit from a visual
  "confidence": string       // "high", "medium", "low"
}

## Rules

1. If the user asks about a store by name, set scope to "location" and include the name in locations.
2. If the user says "all stores" or does not name a store for a ranking, set scope to "all_retail_stores".
3. If the user asks "which store had the highest X per day", the intent is peak_store_daily_revenue, not rank_time_periods.
4. If the user asks "which day had the highest X", the intent is rank_time_periods.
5. If the timeframe is ambiguous, set confidence to "medium" and use the most likely interpretation.
6. "Performance" without a specific metric means multi_metric_summary with metrics ["revenue", "door_count", "net_income", "operating_expenses"].
7. If the question asks about individual people (managers, employees), intent is "unsupported".
8. If the user says "per day" in a ranking context, grain is "day".
9. Default limit for rankings is 5 unless the user specifies a number.
10. "Sale" and "sales" always map to the "revenue" metric.
```

#### Few-Shot Examples (included in planner prompt)

```json
// User: "What store had the highest sale per day for the month of February and how much was it?"
{
  "intent": "peak_store_daily_revenue",
  "metrics": ["revenue"],
  "grain": "day",
  "scope": "all_retail_stores",
  "locations": [],
  "timeframe": {"type": "named_month", "month_name": "February", "year": 2026},
  "timeframe_b": null,
  "limit": 1,
  "sort_direction": "desc",
  "requires_chart": false,
  "confidence": "high"
}

// User: "Compare DeZavala and Blanco for March revenue"
{
  "intent": "compare_locations",
  "metrics": ["revenue"],
  "grain": "month",
  "scope": "location",
  "locations": ["DeZavala", "Blanco"],
  "timeframe": {"type": "named_month", "month_name": "March", "year": 2026},
  "timeframe_b": null,
  "limit": null,
  "sort_direction": "desc",
  "requires_chart": true,
  "confidence": "high"
}

// User: "How did March compare to February for sales?"
{
  "intent": "compare_periods",
  "metrics": ["revenue"],
  "grain": "month",
  "scope": "all_retail_stores",
  "locations": [],
  "timeframe": {"type": "named_month", "month_name": "March", "year": 2026},
  "timeframe_b": {"type": "named_month", "month_name": "February", "year": 2026},
  "limit": null,
  "sort_direction": "desc",
  "requires_chart": true,
  "confidence": "high"
}

// User: "Top 5 days by door count in March"
{
  "intent": "rank_time_periods",
  "metrics": ["door_count"],
  "grain": "day",
  "scope": "all_retail_stores",
  "locations": [],
  "timeframe": {"type": "named_month", "month_name": "March", "year": 2026},
  "timeframe_b": null,
  "limit": 5,
  "sort_direction": "desc",
  "requires_chart": true,
  "confidence": "high"
}

// User: "How is Bandera doing this month?"
{
  "intent": "multi_metric_summary",
  "metrics": ["revenue", "door_count", "net_income", "operating_expenses"],
  "grain": "month",
  "scope": "location",
  "locations": ["Bandera"],
  "timeframe": {"type": "this_month"},
  "timeframe_b": null,
  "limit": null,
  "sort_direction": "desc",
  "requires_chart": false,
  "confidence": "high"
}

// User: "Is revenue up or down from last month?"
{
  "intent": "compare_periods",
  "metrics": ["revenue"],
  "grain": "month",
  "scope": "all_retail_stores",
  "locations": [],
  "timeframe": {"type": "this_month"},
  "timeframe_b": {"type": "last_month"},
  "limit": null,
  "sort_direction": "desc",
  "requires_chart": true,
  "confidence": "high"
}

// User: "Which stores have high traffic but low revenue?"
{
  "intent": "derived_metric",
  "metrics": ["revenue_per_visit"],
  "grain": "period",
  "scope": "all_retail_stores",
  "locations": [],
  "timeframe": {"type": "this_month"},
  "timeframe_b": null,
  "limit": 10,
  "sort_direction": "asc",
  "requires_chart": true,
  "confidence": "medium"
}

// User: "Who manages the Blanco store?"
{
  "intent": "unsupported",
  "metrics": [],
  "grain": null,
  "scope": null,
  "locations": ["Blanco"],
  "timeframe": null,
  "timeframe_b": null,
  "limit": null,
  "sort_direction": null,
  "requires_chart": false,
  "confidence": "high"
}
```

#### Planner Call Implementation

```python
async def plan_request(user_message: str, session: SessionState, store_context: str) -> dict:
    """
    1. Resolve references using session memory
    2. Call GPT-5.4-mini with structured output
    3. Validate the plan against the schema
    4. Resolve timeframes to concrete ISO dates
    5. Resolve store names to LocationIDs
    """
    resolved = resolve_references(user_message, session, store_context)

    response = await client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Session: {session.to_context_string()}\n\nUser: {resolved.text}"}
        ],
        response_format={"type": "json_schema", "json_schema": PLAN_SCHEMA},
        temperature=0.0,
        max_tokens=500,
        timeout=3,  # Hard 3-second timeout for planner
    )

    plan = json.loads(response.choices[0].message.content)
    plan = validate_and_resolve(plan, session, store_context)
    return plan
```

#### Validation Gate

After the LLM returns a plan, `validate_and_resolve()`:

1. Checks `intent` is in the allowed catalog (rejects hallucinated intents)
2. Checks `metrics` are all in the canonical set
3. Resolves `timeframe.type` to concrete ISO start/end dates
4. Resolves `locations` to LocationIDs using fuzzy matching against the location catalog
5. Applies defaults (limit=5, sort_direction="desc", scope="all_retail_stores")
6. If confidence is "low", returns a clarification response instead of proceeding

#### Fallback to V1 Heuristics

If the planner LLM call fails (timeout, quota, malformed output), the system falls back to the V1 regex planner. This ensures the chat never fully breaks even if the LLM is unavailable.

```python
try:
    plan = await plan_request_llm(user_message, session, store_context)
except (TimeoutError, json.JSONDecodeError, ValidationError):
    plan = plan_request_heuristic(user_message, store_context, history)
```

---

## Set-Based SQL Retrieval (retrieval.py)

### The Core Performance Problem

V1's `rank_locations()` calls `_location_metric_total()` once per store. With 30 stores, that is 30 separate SQL round-trips. `rank_revenue_days()` does the same with `_revenue_days_fragment()` per store, parallelized but still N queries.

V2 replaces these with single set-based queries that let SQL Server do the aggregation.

### Revenue Day Ranking (Set-Based)

```sql
-- V2: One query replaces 30 per-store loops
SELECT
    CAST(d.[Date] AS DATE) AS SalesDate,
    CAST(SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18,4)), 0)) AS DECIMAL(18,2)) AS DayTotal
FROM {total_core_table} AS d
INNER JOIN {locations_table} AS loc
    ON {location_join_predicate}
WHERE loc.LocationType IN ('Store', 'Outlet')
  AND loc.IsActive = 1
  {category_filter}
  AND CAST(d.[Date] AS DATE) BETWEEN ? AND ?
GROUP BY CAST(d.[Date] AS DATE)
ORDER BY DayTotal DESC
OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
```

Parameters: `(start_date, end_date, limit)`

This eliminates the Python per-store loop entirely. One query, one round-trip, SQL Server handles the aggregation.

### Store Revenue Ranking (Set-Based)

```sql
SELECT
    loc.LocationID,
    loc.LocationName,
    CAST(SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18,4)), 0)) AS DECIMAL(18,2)) AS MetricValue
FROM {total_core_table} AS d
INNER JOIN {locations_table} AS loc
    ON {location_join_predicate}
WHERE loc.LocationType IN ('Store', 'Outlet')
  AND loc.IsActive = 1
  {category_filter}
  AND CAST(d.[Date] AS DATE) BETWEEN ? AND ?
GROUP BY loc.LocationID, loc.LocationName
ORDER BY MetricValue DESC
OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
```

### Peak Store Daily Revenue (Set-Based)

```sql
SELECT TOP (?)
    loc.LocationID,
    loc.LocationName,
    CAST(d.[Date] AS DATE) AS SalesDate,
    CAST(SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18,4)), 0)) AS DECIMAL(18,2)) AS DayRevenue
FROM {total_core_table} AS d
INNER JOIN {locations_table} AS loc
    ON {location_join_predicate}
WHERE loc.LocationType IN ('Store', 'Outlet')
  AND loc.IsActive = 1
  {category_filter}
  AND CAST(d.[Date] AS DATE) BETWEEN ? AND ?
GROUP BY loc.LocationID, loc.LocationName, CAST(d.[Date] AS DATE)
ORDER BY DayRevenue DESC
```

This directly answers "What store had the highest sale per day for February?" in one query.

### Monthly Financial Ranking (Set-Based)

```sql
SELECT
    loc.LocationID,
    loc.LocationName,
    CAST(SUM(ISNULL(d.[{metric_column}], 0)) AS DECIMAL(18,2)) AS MetricValue
FROM {monthly_financial_table} AS d
INNER JOIN {locations_table} AS loc
    ON {unit_name_join_predicate}
WHERE DATEFROMPARTS(d.[Year], d.[Month], 1) BETWEEN
      DATEFROMPARTS(YEAR(?), MONTH(?), 1) AND DATEFROMPARTS(YEAR(?), MONTH(?), 1)
  AND loc.LocationType IN ('Store', 'Outlet')
  AND loc.IsActive = 1
GROUP BY loc.LocationID, loc.LocationName
ORDER BY MetricValue DESC
OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
```

### Network Period Comparison (Set-Based)

```sql
-- Period A
SELECT CAST(SUM(ISNULL(d.[{metric_column}], 0)) AS DECIMAL(18,2)) AS PeriodTotal
FROM {source_table} AS d
INNER JOIN {locations_table} AS loc ON {join_predicate}
WHERE {date_filter_a} AND loc.LocationType IN ('Store', 'Outlet') AND loc.IsActive = 1

-- Period B (same structure, different date params)
```

Two queries instead of 2 × N.

### Retrieval Function Registry

```python
RETRIEVAL_REGISTRY = {
    "location_summary":          retrieve_location_summary,
    "compare_locations":         retrieve_compare_locations,
    "rank_locations":            retrieve_rank_locations,
    "rank_time_periods":         retrieve_rank_time_periods,
    "peak_store_daily_revenue":  retrieve_peak_store_daily_revenue,
    "trend_summary":             retrieve_trend_summary,
    "metric_breakdown":          retrieve_metric_breakdown,
    "multi_metric_summary":      retrieve_multi_metric_summary,
    "compare_periods":           retrieve_compare_periods,
    "correlation_check":         retrieve_correlation,
    "derived_metric":            retrieve_derived_metric,
    "revenue_door_series":       retrieve_revenue_door_series,
    "data_catalog":              retrieve_data_catalog,
    "map_context_summary":       retrieve_map_context,
}

def run_retrieval(plan: dict, store_context: str) -> tuple[str, dict]:
    intent = plan.get("intent")
    fn = RETRIEVAL_REGISTRY.get(intent)
    if fn is None:
        return None, None
    return fn(plan, store_context)
```

---

## Conversational Composer (composer.py + composer_prompt.py)

### V2 System Prompt

```
You are the GWSA GeoAnalytics assistant for Goodwill Industries of San Antonio. You help operations
staff, regional managers, and executives understand store performance through natural conversation.

## How to Write

Write like a knowledgeable colleague explaining data over coffee. Use natural, flowing sentences.
Lead with the answer, then context, then nuance. Examples of good tone:

- "Fredericksburg Rd had the strongest day in February, pulling in $18,742 on the 14th — a Saturday,
  which tracks with the typical weekend bump."
- "Revenue is up 8% from February to March across the network, driven mostly by the south-side stores."
- "Door count and revenue moved together pretty closely in March (r = 0.82), so traffic was converting
  into sales consistently."

## How NOT to Write

Never output mechanical labels, rigid templates, or database jargon:

- BAD: "Leader: Fredericksburg Rd. Value: $18,742.63. Date: 2026-02-14. Grain: daily."
- BAD: "Data Action: peak_store_daily_revenue. Source: JS_API.dbo.TotalCoreTableFinal."
- BAD: "Based on the retrieved evidence payload, the following analysis has been computed:"

## Non-Negotiable Rules

1. Every factual claim must come from the structured analytics data in this request. Do not invent
   figures, stores, dates, rankings, or causal explanations the data does not support.
2. Use exact values, store names, and date ranges from the payload. You may round for readability
   ($18,742.63 → "$18,743" or "about $18,700") but do not change the underlying number.
3. If the data partially answers the question, say what you can answer and what is missing — in
   plain language, not error codes.
4. Keep it concise when a short answer suffices. Expand when the question is complex or the data
   has interesting patterns worth calling out.
5. Never expose SQL, credentials, connection strings, API keys, table names, or internal config
   to the user.
6. Do not name individual store managers. Refer to roles only.
7. When the evidence includes a source object, you may mention the data type casually ("from the
   daily sales feed") but never format it as a citation block or database reference.
8. End with 2-3 natural follow-up suggestions that the data actually supports. Frame them as
   questions the user might want to ask next, not as a bulleted menu.

## Handling Data Gaps

When the data cannot fully answer the question:

- "I can tell you the monthly totals for March, but daily breakdowns for that store aren't
  available yet in this dataset."
- "That would need personnel data that this dashboard doesn't cover — I work from sales, traffic,
  and financial summaries."

Never say "unsupported intent" or "data gap code" to the user.

## Handling Partial or Empty Data

- If periods list is empty: "There are no daily records matching that range — this sometimes
  happens when the store had no transactions logged for those dates."
- If a metric is null or zero: call it out naturally rather than silently omitting it.

## Follow-Up Suggestions

Offer follow-ups that make operational sense given the data just shown. Examples:

- After showing a top revenue day: "Want to see which store drove most of that, or compare it
  to the same day last month?"
- After a store comparison: "I could also pull the trend for both over the last 6 months if
  that would help."
- After a ranking: "Want me to add door count to the comparison, or break down the top store
  by day?"
```

### Prompt Assembly

```python
def build_composer_prompt(
    user_message: str,
    session: SessionState,
    plan: dict,
    data_action: str,
    analytics_data: dict,
    data_gap: str,
    history: list,
) -> list[dict]:
    """Build the messages array for the answer composer LLM call."""

    system = COMPOSER_SYSTEM_PROMPT

    memory_context = build_memory_context(session, history)

    evidence_json = json.dumps(
        trim_evidence(analytics_data),
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )

    user_content = f"""Context:
Active store: {session.selected_store_name or "(none)"}
Conversation state: {memory_context}

Analytics action: {data_action or "(none)"}
Evidence:
{evidence_json if analytics_data else "(none)"}

Data gaps: {data_gap or "None"}

User question: {user_message}"""

    messages = [{"role": "system", "content": system}]

    # Include last 4 turns for conversational continuity
    for item in history[-4:]:
        role = item.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": str(item.get("content", ""))[:500]})

    messages.append({"role": "user", "content": user_content})
    return messages
```

---

## Metric Vocabulary (schemas.py)

### Canonical Metrics

| Canonical Name | User Aliases | Primary Source | Available Grains |
|---|---|---|---|
| `revenue` | sales, sale value, core sales, revenue, total revenue, net revenue, income (when alone) | TotalCoreTableFinal (daily), RetailStoreMonthlyFinancialSummary (monthly) | daily, monthly |
| `door_count` | door count, visits, visitors, traffic, donor visits, foot traffic, footfall | PeopleCounter.dbo.PCounter | daily |
| `net_income` | net income, profit, bottom line, net profit | RetailStoreMonthlyFinancialSummary | monthly |
| `operating_expenses` | expenses, operating expenses, opex, total expenses, overhead | RetailStoreMonthlyFinancialSummary | monthly |
| `personnel_expenses` | payroll, labor, personnel expense, staffing expense, labor cost, wages | RetailStoreMonthlyFinancialSummary | monthly |
| `expense_ratio` | expense ratio, cost ratio, expense percent, cost-to-revenue, efficiency ratio | RetailStoreMonthlyFinancialSummary | monthly |
| `revenue_per_visit` | revenue per visitor, sales per visit, conversion, dollars per visit, spend per visitor | Derived: revenue / door_count | daily, monthly |

### Metric Resolution Rules

1. "Sales" and "sale value" always → `revenue` unless a future POS line-item metric is added.
2. "Income" alone → `revenue`. "Net income" → `net_income`.
3. "Expenses" alone → `operating_expenses`. "Personnel expenses" / "payroll" → `personnel_expenses`.
4. "Performance" → multi-metric: `[revenue, door_count, net_income, operating_expenses]`.
5. "Traffic" → `door_count` unless paired with "revenue" in a derived context.
6. "Conversion" or "per visit" → `revenue_per_visit` (derived).
7. "Efficiency" → `expense_ratio`.

---

## Intent Catalog (schemas.py)

### Complete Intent List

| Intent | Description | Example Questions | Grain | Requires |
|---|---|---|---|---|
| `location_summary` | Overview of one store | "How is DeZavala doing?" / "Tell me about Bandera" | auto | store reference |
| `compare_locations` | Compare 2 stores on a metric | "Compare DeZavala vs Blanco for March" / "Which is better, Bandera or Fredericksburg?" | month or day | 2 store names, metric |
| `rank_locations` | Rank stores by a metric | "Top 5 stores by revenue" / "Which store has lowest expenses?" | period | metric, timeframe |
| `rank_time_periods` | Rank calendar days/weeks | "Which day had highest sales in March?" / "Top 5 busiest days" | day | metric, timeframe |
| `peak_store_daily_revenue` | Best single store-day combination | "What store had the highest sale per day for February?" | day | timeframe |
| `trend_summary` | Metric trend over time | "Show revenue trend for last 12 months" / "How has Bandera been doing?" | month | store reference |
| `metric_breakdown` | Break a metric down by store | "Break down March revenue by store" / "Revenue by store for last month" | period | metric, timeframe |
| `multi_metric_summary` | Multiple metrics for one store | "Sales, door count, income, expenses for March" / "Full performance report for DeZavala" | month | store reference, timeframe |
| `compare_periods` | Compare two time periods | "March vs February" / "Is revenue up from last month?" | month | metric, two timeframes |
| `correlation_check` | Do two metrics track together? | "Did traffic drive revenue in March?" / "Revenue vs door count correlation" | day | timeframe |
| `derived_metric` | Computed metric ranking | "Revenue per visitor by store" / "Which stores convert best?" | period | timeframe |
| `revenue_door_series` | Aligned daily revenue + door count | "Show daily revenue and traffic for Bandera in March" | day | store reference, timeframe |
| `data_catalog` | What can the assistant answer? | "What data do you have?" / "Help" / "What can I ask?" | n/a | nothing |
| `map_context_summary` | Donor geography | "Where are donors coming from for this store?" | n/a | store reference |
| `unsupported` | Outside available data | "Who manages Blanco?" / "What's the weather?" | n/a | nothing |

### New Intents to Add in V2

| Intent | Example | Why Missing in V1 |
|---|---|---|
| `quarter_summary` | "How did Q1 go?" | V1 only understands named months, not quarters |
| `ytd_summary` | "Year to date revenue" | V1 parse_timeframe handles "ytd" but no dedicated intent |
| `week_summary` | "How was last week?" | V1 has no week-level timeframe parsing |
| `anomaly_flag` | "Anything unusual in March?" | Requires statistical baseline, Phase 2 |
| `forecast_question` | "What will April revenue look like?" | Requires forecasting model, Phase 3 |

---

## Timeframe Resolution

### Supported Timeframe Types

| User Says | Resolved Type | Start | End |
|---|---|---|---|
| "March" / "March 2026" | named_month | 2026-03-01 | 2026-03-31 |
| "this month" / "current month" | this_month | first of current month | today |
| "last month" / "previous month" | last_month | first of previous month | last day of previous month |
| "last 30 days" / "past 30 days" | last_n_days (n=30) | today minus 29 | today |
| "last week" | last_n_days (n=7) | Monday of last week | Sunday of last week |
| "this year" / "YTD" / "year to date" | ytd | Jan 1 of current year | today |
| "last year" | last_year | Jan 1 of previous year | Dec 31 of previous year |
| "Q1" / "first quarter" | quarter | Jan 1 | Mar 31 |
| "Q1 2026" | quarter | 2026-01-01 | 2026-03-31 |
| "last quarter" | last_quarter | first day of previous quarter | last day of previous quarter |
| "February vs March" | two timeframes | (resolved separately for compare_periods) |
| "2025" | full_year | 2025-01-01 | 2025-12-31 |

### Quarter Resolution Logic (New in V2)

```python
QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}

def resolve_quarter(quarter_num: int, year: int) -> dict:
    start_month, end_month = QUARTER_MONTHS[quarter_num]
    last_day = monthrange(year, end_month)[1]
    return {
        "start": date(year, start_month, 1).isoformat(),
        "end": date(year, end_month, last_day).isoformat(),
        "label": f"Q{quarter_num} {year}",
    }
```

---

## Response Contract

### JSON Envelope

```json
{
  "reply": "Natural language answer text...",
  "response_type": "answer",
  "data_action": "peak_store_daily_revenue",
  "data": { ... },
  "sources": [
    {
      "name": "Daily Core Revenue",
      "grain": "daily",
      "metric": "Revenue",
      "date_range": "2026-02-01 to 2026-02-28"
    }
  ],
  "followups": [
    "Break that day down by store",
    "Show the top 5 revenue days in February",
    "How does that compare to January?"
  ],
  "chart": {
    "type": "bar",
    "title": "Top Revenue Days — February 2026",
    "x_key": "date",
    "y_key": "metric_value",
    "y_label": "Revenue ($)",
    "rows": [...]
  },
  "data_gap": null,
  "confidence": "high",
  "plan_used": {
    "intent": "peak_store_daily_revenue",
    "metrics": ["revenue"],
    "grain": "day",
    "scope": "all_retail_stores"
  }
}
```

### Response Types

| Type | When | What the User Sees |
|---|---|---|
| `answer` | Data fully answers the question | Full conversational answer with numbers |
| `partial_answer` | Data answers part of the question | Answer + explanation of what is missing |
| `data_gap` | No approved action supports the request | Friendly explanation of what data is available |
| `clarification_needed` | Ambiguous store, metric, or timeframe | "Did you mean Bandera Retail Store or Bandera Rd Donation Station?" |
| `provider_error` | LLM failed after retrieval | Fallback answer with raw data summary |
| `demo` | No AI provider configured | Static demo response |

### Follow-Up Suggestion Engine (followups.py)

Follow-ups are generated based on the intent and data just returned, not by the LLM:

```python
FOLLOWUP_TEMPLATES = {
    "rank_locations": [
        "Show the trend for {leader_name} over the last 6 months",
        "Break down {leader_name}'s {metric} by day for {timeframe_label}",
        "How does {metric} compare to door count for the top stores?",
    ],
    "rank_time_periods": [
        "Break that day down by store",
        "Show the top {next_limit} {metric} days for {timeframe_label}",
        "How does {timeframe_label} compare to the previous month?",
    ],
    "peak_store_daily_revenue": [
        "Show all of {leader_name}'s daily revenue for {timeframe_label}",
        "Which other stores had strong days in {timeframe_label}?",
        "How does {timeframe_label} total compare to the month before?",
    ],
    "compare_locations": [
        "Add door count to the comparison",
        "Show the monthly trend for both stores",
        "Which store has better revenue per visitor?",
    ],
    "compare_periods": [
        "Break down the change by store",
        "Show the daily trend for both periods",
        "Did door count change in the same direction?",
    ],
    "location_summary": [
        "Show the trend for the last 12 months",
        "How does this store rank against others?",
        "Compare this store with {random_other_store}",
    ],
    "multi_metric_summary": [
        "How do these metrics compare to last month?",
        "Rank all stores by {primary_metric} for {timeframe_label}",
        "Show the trend for the last 6 months",
    ],
    "trend_summary": [
        "Which month was strongest?",
        "Compare the last two months",
        "How does this store rank against the network?",
    ],
}
```

Follow-ups are populated with real values from the response data (store names, metrics, timeframes) so the user can click them directly.

---

## Chart Payloads

When `requires_chart` is true in the plan, the retrieval function includes a `chart` object in the response:

```python
CHART_CONFIGS = {
    "rank_locations": {"type": "horizontal_bar", "x_key": "metric_value", "y_key": "location_name"},
    "rank_time_periods": {"type": "bar", "x_key": "date", "y_key": "metric_value"},
    "peak_store_daily_revenue": {"type": "bar", "x_key": "location_name", "y_key": "metric_value"},
    "trend_summary": {"type": "line", "x_key": "PeriodMonth", "y_key": "NetRevenue"},
    "compare_locations": {"type": "grouped_bar", "x_key": "location_name", "y_key": "metric_value"},
    "compare_periods": {"type": "grouped_bar", "x_key": "label", "y_key": "value"},
    "correlation_check": {"type": "scatter", "x_key": "network_revenue", "y_key": "network_door_count"},
    "revenue_door_series": {"type": "dual_axis_line", "x_key": "date", "y1_key": "revenue", "y2_key": "door_count"},
}
```

The frontend reads `chart.type` and renders using the existing charting library (Recharts or Chart.js).

---

## Data Source Routing

| Intent + Metric | Source Table | Grain |
|---|---|---|
| Any revenue, grain=day | TotalCoreTableFinal | daily rows grouped by date |
| Any revenue, grain=month | RetailStoreMonthlyFinancialSummary | monthly rollup |
| net_income, operating_expenses, personnel_expenses, expense_ratio | RetailStoreMonthlyFinancialSummary | monthly only |
| door_count, any grain | PeopleCounter.dbo.PCounter | daily rows grouped by date |
| revenue_per_visit | TotalCoreTableFinal + PCounter | daily or monthly (derived) |
| trend_summary | RetailStoreMonthlyFinancialSummary + PCounter | monthly |
| donor geography | dbo.DonorAddresses | point-level |
| store metadata | Locations table or static list | n/a |

### Source Selection Logic

```python
def select_source(metric: str, grain: str, timeframe: dict) -> str:
    if metric == "door_count":
        return "pcounter"
    if metric in ("net_income", "operating_expenses", "personnel_expenses", "expense_ratio"):
        return "monthly_financial"
    if metric == "revenue":
        if grain == "day":
            return "total_core"
        return "monthly_financial"
    if metric == "revenue_per_visit":
        return "total_core+pcounter"
    return "monthly_financial"
```

---

## Error Handling and Graceful Degradation

### Timeout Strategy

| Stage | Timeout | Fallback |
|---|---|---|
| Planner LLM call | 3 seconds | Fall back to V1 regex heuristics |
| SQL retrieval | 10 seconds | Return data_gap: "query_timeout" |
| Composer LLM call | 8 seconds | Return quota_fallback_reply with raw data |
| Total request | 15 seconds | Return whatever has completed so far |

### Quota / Rate Limit Handling

```python
async def compose_answer(messages, data_action, analytics_data):
    try:
        response = await client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=messages,
            timeout=8,
        )
        return response.choices[0].message.content
    except RateLimitError:
        return quota_fallback_reply(data_action, analytics_data)
    except Timeout:
        # Retry once with a shorter prompt (drop history, keep evidence)
        try:
            short_messages = [messages[0], messages[-1]]  # system + latest user only
            response = await client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=short_messages,
                timeout=5,
            )
            return response.choices[0].message.content
        except Exception:
            return quota_fallback_reply(data_action, analytics_data)
```

### Provider Failover

```
Primary:   Azure OpenAI (deployment from AZURE_OPENAI_DEPLOYMENT)
Emergency: Raw data summary (no LLM)
```

---

## Complete Question Coverage Matrix

These are the questions a normal person would ask, organized by complexity. Every one must produce a useful answer.

### Tier 1: Simple Lookups (single metric, single scope)

| Question | Intent | Metric | Notes |
|---|---|---|---|
| "What was total revenue in March?" | rank_locations or location_summary | revenue | Network total if no store selected |
| "How many visitors did we get last month?" | rank_time_periods or location_summary | door_count | |
| "What is our net income for March?" | multi_metric_summary | net_income | Monthly financial source |
| "What are operating expenses this month?" | multi_metric_summary | operating_expenses | |
| "What's the expense ratio for Bandera?" | location_summary or multi_metric_summary | expense_ratio | |
| "Total payroll last month?" | multi_metric_summary | personnel_expenses | |

### Tier 2: Rankings (which store / which day)

| Question | Intent | Notes |
|---|---|---|
| "Which store had the highest revenue in March?" | rank_locations | |
| "Top 5 stores by door count" | rank_locations | |
| "Which day had the most sales in February?" | rank_time_periods | |
| "Top 3 busiest days this month" | rank_time_periods | metric=door_count |
| "Which store has the lowest expense ratio?" | rank_locations | sort_direction=asc |
| "What store had the highest sale per day for February and how much was it?" | peak_store_daily_revenue | The question that was failing in V1 |
| "Which stores have the highest operating expenses?" | rank_locations | metric=operating_expenses |
| "Lowest performing stores this quarter" | rank_locations | metric=revenue, sort_direction=asc |

### Tier 3: Comparisons

| Question | Intent | Notes |
|---|---|---|
| "Compare DeZavala and Blanco for March" | compare_locations | |
| "How did March compare to February?" | compare_periods | |
| "Is revenue up or down from last month?" | compare_periods | Implicit: this month vs last month |
| "Compare Q1 to Q1 last year" | compare_periods | New: quarter support |
| "DeZavala vs Blanco, who had more traffic?" | compare_locations | metric=door_count |
| "Did expenses go up from February?" | compare_periods | metric=operating_expenses |

### Tier 4: Trends and Patterns

| Question | Intent | Notes |
|---|---|---|
| "Show revenue trend for the last 12 months" | trend_summary | |
| "How has Bandera been doing?" | trend_summary | Implicit: last 12 months |
| "Did door count track revenue in March?" | correlation_check | |
| "Do more visitors mean more sales?" | correlation_check | |
| "Revenue per visitor by store" | derived_metric | |
| "Which stores convert visitors best?" | derived_metric | revenue_per_visit, sort desc |
| "Show daily revenue and traffic for DeZavala in March" | revenue_door_series | |

### Tier 5: Multi-Metric and Breakdowns

| Question | Intent | Notes |
|---|---|---|
| "Give me everything for Bandera in March" | multi_metric_summary | All metrics |
| "How is DeZavala doing this month?" | multi_metric_summary | "Performance" = all metrics |
| "Break down March revenue by store" | metric_breakdown | |
| "Show me sales, expenses, and profit for Q1" | multi_metric_summary | |
| "Which stores had high traffic but low revenue?" | derived_metric | revenue_per_visit, sort asc |

### Tier 6: Contextual and Follow-Up

| Question | Intent | Notes |
|---|---|---|
| "What about door count?" | (carry forward from last question) | Memory resolves metric swap |
| "And for March?" | (carry forward) | Memory resolves timeframe swap |
| "Compare it with Blanco" | compare_locations | "it" = selected store from memory |
| "Sure, do that" | (re-run suggested follow-up) | Memory tracks pending follow-ups |
| "Same thing but for last month" | (carry forward with timeframe shift) | |
| "This store" / "the selected one" | (use map-selected store) | From store_context |

### Tier 7: Meta and Edge Cases

| Question | Intent | Notes |
|---|---|---|
| "What data can I ask about?" | data_catalog | |
| "Help" | data_catalog | |
| "Who manages Blanco?" | unsupported | No manager names |
| "Why did revenue drop?" | partial_answer | Describe what changed, do not invent causes |
| "What will April look like?" | unsupported (Phase 3: forecast) | |
| "What's the weather?" | unsupported | |
| Random greeting: "Hey" / "Hello" | greeting | Friendly response + capability overview |

---

## LLM Model Selection

### GPT-5.4-mini — Current Model

GPT-5.4-mini is already a strong model for this use case. The performance issues are not the model itself but how the pipeline uses it:

- **V1 problem**: One large LLM call does everything (intent classification + answer generation) from a bloated prompt with raw evidence. The model spends tokens figuring out what the user wants instead of explaining pre-retrieved data.
- **V2 fix**: Split into two focused calls. The planner call is tiny (~800 input tokens, ~200 output) and uses structured output / JSON mode so the model returns a clean plan. The composer call is larger but receives pre-trimmed evidence and a tight system prompt focused on tone.

GPT-5.4-mini supports structured output (JSON schema enforcement), which makes the planner call highly reliable — the model cannot return malformed plans.

The planner call uses ~800 tokens input and ~200 tokens output. The composer call uses ~2,000 tokens input and ~300 tokens output. Total cost per chat turn is minimal.

### Two-Call Architecture

| Call | Model | Purpose | Timeout | Token Budget |
|---|---|---|---|---|
| Planner | GPT-5.4-mini | Intent + slot extraction | 3s | 500 output |
| Composer | GPT-5.4-mini | Natural language answer | 8s | 800 output |

Total LLM latency target: under 4 seconds for both calls combined. SQL retrieval should add under 1 second with set-based queries.

---

## Frontend Changes

### Response Rendering

The frontend currently shows `reply` text and a debug `Data Action` toggle. V2 adds:

1. **Follow-up chips**: Clickable buttons below the answer that send the follow-up question as a new user message.
2. **Source pill**: Small expandable badge showing data source, grain, and date range.
3. **Inline chart**: Rendered from the `chart` payload when present (bar, line, scatter).
4. **Data gap banner**: Amber banner explaining what data is missing (not an error, just information).
5. **Confidence indicator**: Subtle dot (green/yellow/red) for high/medium/low confidence.
6. **Typing indicator**: Show "Analyzing..." while the planner runs, "Retrieving data..." during SQL, "Composing answer..." during the composer call.

### Chat Input Enhancements

1. **Suggested questions**: On first load, show 4 starter questions as chips:
   - "How are stores doing this month?"
   - "Which store had the highest revenue in March?"
   - "Compare the top stores"
   - "What data can I ask about?"
2. **Context badge**: Show the currently selected store name above the input field.
3. **Quick metric buttons**: Optional row of metric shortcuts (Revenue, Traffic, Expenses, Trends).

---

## Implementation Roadmap

### Phase 1 — Performance and Core Quality (Weeks 1-2)

1. Replace per-store SQL loops with set-based queries for all ranking intents
2. Restructure the GPT-5.4-mini usage into two focused calls (planner + composer)
3. Implement the two-call architecture (planner + composer)
4. Update the composer system prompt for conversational tone
5. Add follow-up suggestions (template-based, not LLM-generated)
6. Add timeout/retry logic with graceful degradation
7. Wire up the V1 heuristic planner as a fallback

**Expected impact**: Response time drops from 8-15 seconds to 3-6 seconds. Answers sound natural instead of robotic.

### Phase 2 — Intent Coverage and Memory (Weeks 3-4)

1. Implement LLM-assisted planner with structured output
2. Add session memory (SessionState dataclass, reference resolution)
3. Add quarter and week timeframe resolution
4. Add metric_breakdown intent and retrieval
5. Add multi_metric_summary set-based retrieval
6. Add correlation_check set-based retrieval
7. Expand the planner few-shot examples to cover all Tier 1-5 questions

**Expected impact**: The assistant handles 90%+ of natural business questions instead of 40%.

### Phase 3 — Frontend and Polish (Weeks 5-6)

1. Render follow-up chips in the chat UI
2. Add source pills and confidence indicators
3. Render chart payloads (bar, line, scatter, dual-axis)
4. Add starter question chips on first load
5. Add typing/progress indicators during the pipeline stages
6. Persist session state in browser sessionStorage or a lightweight backend session
7. Add data gap banner styling

**Expected impact**: The chat feels like a modern analytics assistant, not a text box bolted onto a map.

### Phase 4 — Testing and Hardening (Week 7)

1. Write integration tests for every question in the coverage matrix
2. Add planner accuracy tests (input question → expected intent + slots)
3. Add retrieval correctness tests (plan → expected SQL output)
4. Add composer tone tests (no database jargon, no mechanical labels)
5. Load test the set-based queries under concurrent users
6. Add monitoring for planner/composer latency and error rates

---

## Acceptance Test Questions

Use these to validate the V2 system. Every question should produce a correct, conversational answer.

### Must Pass (Blocking)

1. "What store had the highest sale per day for the month of February and how much was it?"
2. "Which store had the highest revenue in March 2026?"
3. "For March 2026, which day had the highest sales across all retail stores?"
4. "Show the top 5 sales days in March."
5. "Compare DeZavala and Blanco Retail Store for March revenue."
6. "How did March compare to February for sales?"
7. "How is Bandera doing this month?"
8. "Is revenue up or down from last month?"
9. "Which stores have the highest operating expenses?"
10. "What data can I ask about?"
11. "Who manages Blanco?" → must refuse gracefully, no manager names
12. "Why did revenue drop?" → must describe only observed data, not invent causes

### Should Pass (Important)

13. "Top 3 stores by door count this month"
14. "Revenue per visitor for each store in March"
15. "Did door count track revenue in March?"
16. "Show the revenue trend for Fredericksburg over the last 12 months"
17. "Break down March revenue by store"
18. "Sales, door count, net income, and expenses for DeZavala in March"
19. "Which day had the highest door count in February?"
20. "Compare Q1 2026 to Q1 2025"

### Contextual Follow-Up (Memory Test)

21. User: "Which store had the highest revenue in March?" → Answer.
    User: "What about door count?" → Should reuse March timeframe and rank_locations intent, switch metric to door_count.
22. User: "How is DeZavala doing this month?" → Answer.
    User: "Compare it with Blanco" → Should compare DeZavala vs Blanco with same timeframe.
23. User: "Top 5 stores by revenue in March" → Answer with follow-ups.
    User: "Sure, show the trend" → Should execute the first follow-up suggestion.

### Tone Test (Manual Review)

24. No answer should contain the words: "Leader:", "Value:", "Data grain:", "Retrieved evidence:", "Data Action:", "SQL_", "dbo.", "TotalCoreTableFinal", or "RetailStoreMonthlyFinancialSummary".
25. Every answer should read like a sentence a colleague would say, not a database report.
26. Follow-up suggestions should be phrased as natural questions, not technical commands.

---

## Summary of Key Decisions

1. **Two LLM calls per turn, not one.** The planner call is fast and cheap (3s, ~200 output tokens). It replaces fragile regex heuristics with reliable structured output. The composer call is the expensive one but benefits from having clean, pre-retrieved evidence.

2. **Set-based SQL, not per-store loops.** The single biggest performance win. One GROUP BY query replaces 30 sequential queries.

3. **LLM planner with heuristic fallback.** If the LLM is unavailable, the V1 regex planner still works. Users get a degraded but functional experience instead of an error.

4. **Session memory, not persistent memory.** V2 tracks state within a chat session. Cross-session memory (remembering a user's favorite store across visits) is a Phase 4 feature that requires a user identity system.

5. **Conversational tone enforced by prompt, not code.** The composer prompt is detailed and opinionated about tone. The code does not try to format the answer — it trusts the LLM to write naturally given good evidence and clear instructions.

6. **Follow-ups are template-based, not LLM-generated.** This keeps follow-up suggestions fast, predictable, and guaranteed to map to supported intents. The LLM can mention them naturally in prose, but the clickable chips come from templates.

7. **Charts are payload-driven, not LLM-rendered.** The backend tells the frontend what chart to render. The LLM never generates chart code or SVG.
