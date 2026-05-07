# GWSA GeoAnalytics AI Model V3 — Implementation Fixes

## What This Document Is

V2 was a design spec. It described what the system should do but not what code to change. The screenshots you sent are the result: nothing actually changed. The planner still uses regex, the composer still produces "Leader: Culebra ✅", and daily questions still fail.

This document identifies the exact code-level root causes and provides the exact fixes. It is organized by problem, not by module.

---

## Problem 1: Daily Questions Fail ("I'd need daily transaction data")

### What the user asks

> "On which date/day in February did Potranco Rd Retail Store had the highest sale?"

### What V1 returns

> "The provided analytics only includes February 2026 total revenue by location, not daily sales by date or day of week."

### Root cause (traced through actual code)

In `planner.py`, the function `wants_rank_time_periods()` has this guard on line ~3:

```python
if re.search(r"\b(which|what)\s+store\b", t) and not re.search(r"\b(which|what)\s+(day|date)\b", t):
    return False
```

The user's message contains "Potranco Rd Retail **Store**". The regex `\b(which|what)\s+store\b` does NOT match because "which" is not immediately before "store" — but the word "store" appears in the location name, and the planner's `match_store_names()` resolves "Potranco Rd Retail Store" successfully.

The real problem: the decision cascade in `plan_request()` (line ~487) checks `wants_peak_store_single_day_revenue()` which requires BOTH `re.search(r"\b(which|what)\s+store\b", t)` AND a "single day" pattern. The user says "which date/day" not "which store", so this returns False.

Then `wants_rank_time_periods()` is checked. It sees "which date" and would return True, but the question also contains the word "store" in "Potranco Rd Retail Store" and the function's first guard blocks it because it thinks the user is asking "which store" not "which day."

The planner falls through to `rank_ok` → `rank_locations` → monthly financial summary → no daily data → "I'd need daily transaction data."

**The daily data exists in TotalCoreTableFinal. The planner just routes to the wrong table.**

### Fix

The regex planner cannot reliably distinguish "Potranco Rd Retail Store" (location name containing "store") from "which store had the highest" (asking about stores). This is a fundamental limitation of regex-based intent classification.

**Immediate fix (keeps regex planner, fixes the specific bug):**

In `planner.py`, `wants_rank_time_periods()`, change the guard to check for "which/what store" as a QUESTION pattern (which/what + store within 3 words), not just the presence of both words:

```python
def wants_rank_time_periods(user_message: str) -> bool:
    t = (user_message or "").strip().lower()
    if not t:
        return False
    
    # Only block if the user is ASKING "which store" / "what store" as the question,
    # not if "store" appears in a location name like "Potranco Rd Retail Store"
    asks_which_store = bool(re.search(r"\b(which|what)\s+store\b", t))
    asks_which_day = bool(re.search(r"\b(which|what)\s+(day|date)\b", t))
    
    # If asks both "which store" AND "which day" → day intent wins (they want the day)
    # If asks "which store" but NOT "which day" → not a time-period question
    if asks_which_store and not asks_which_day:
        return False
    
    # ... rest of the function unchanged
```

Also add a new intent detection for "store + day + highest" questions that currently fall through:

```python
def wants_store_best_day(user_message: str) -> bool:
    """Detect: 'On which day did [store name] have the highest sale?'"""
    t = (user_message or "").strip().lower()
    has_day_ref = bool(re.search(r"\b(day|date|when)\b", t))
    has_superlative = bool(re.search(r"\b(highest|best|most|peak|top|biggest|strongest)\b", t))
    has_money = any(k in t for k in ("sale", "sales", "revenue"))
    return has_day_ref and has_superlative and has_money
```

Then in `plan_request()`, add this before the `wants_peak_store_single_day_revenue` check:

```python
elif wants_store_best_day(text_raw) and len(store_names) == 1 and timeframe:
    intent = "peak_store_daily_revenue"
    action = "peak_store_daily_revenue"
    grain = "store_day"
```

**Proper fix (replaces regex planner entirely):**

Replace the regex planner with an LLM planner call. This is described in full below under "Problem 5."

---

## Problem 2: Robotic Tone ("Leader: Culebra Retail Store ✅")

### What the user asks

> "Compare door counts for Fredericksburg vs Culebra"

### What V1 returns

```
Here's the door count comparison for 2026-04-08 to 2026-05-07:

- Culebra Retail Store: 24,811 doors
- Fredericksburg Retail Store: 23,433 doors

Difference: Culebra had 1,378 more doors than Fredericksburg.

Leader: Culebra Retail Store ✅
```

### Root cause

Three things produce this output:

**1. The evidence JSON contains structured labels the LLM mirrors.**

The `compare_locations()` function in `queries.py` returns:
```json
{
  "metric": "door_count",
  "locations": [...],
  "leader": {"location_name": "Culebra Retail Store", "metric_value": 24811}
}
```

The word "leader" in the data payload directly encourages the LLM to output "Leader:" in its response. LLMs mirror the structure of their input.

**2. The user prompt uses mechanical labels.**

`composer.py` `build_response_prompt()` constructs:
```
Approved analytics action:
compare_locations:door_count

Retrieved evidence:
{"metric":"door_count","locations":[...],"leader":{"location_name":"Culebra"...}}

Data gaps:
None.

User question:
Compare door counts for Fredericksburg vs Culebra
```

These labels ("Approved analytics action:", "Retrieved evidence:", "Data gaps:") prime the LLM to respond with similar structured labels.

**3. The system prompt says don't, but the data format says do.**

The system prompt in `prompts.py` says: "Avoid mechanical labels such as 'Leader:', 'Value:'". But the evidence payload literally contains fields called `leader` and `metric_value`. The LLM sees both instructions simultaneously — and the structured data wins because it is more concrete than the abstract instruction.

### Fix

**Fix 1: Rename the JSON fields the LLM sees.**

In `composer.py`, add a function that sanitizes the evidence payload before the LLM sees it:

```python
def _humanize_evidence(data: dict) -> dict:
    """Rename machine-oriented fields so the LLM doesn't mirror them."""
    if not isinstance(data, dict):
        return data
    out = {}
    for key, value in data.items():
        # Rename fields that produce robotic output
        new_key = key
        if key == "leader":
            new_key = "top_result"
        if key == "metric_value":
            new_key = "amount"
        if key == "location_name":
            new_key = "store"
        if key == "metric":
            new_key = "measure"
        
        if isinstance(value, dict):
            out[new_key] = _humanize_evidence(value)
        elif isinstance(value, list):
            out[new_key] = [_humanize_evidence(v) if isinstance(v, dict) else v for v in value]
        else:
            out[new_key] = value
    return out
```

Then in `build_response_prompt()`, use `_humanize_evidence(data)` instead of raw `data`.

**Fix 2: Rewrite the user prompt to not use mechanical labels.**

Replace the current `build_response_prompt()`:

```python
def build_response_prompt(
    user_message: str,
    store_context: Optional[str],
    history: list,
    data_action: Optional[str],
    data: Optional[dict],
    data_gap_description: str,
) -> str:
    dashboard = (store_context or "").strip() or "(none selected)"
    memory_summary = summarize_history(history)

    parts = []
    parts.append(f"The user is viewing: {dashboard}")
    
    if memory_summary and memory_summary != "(no prior turns in this session summary)":
        parts.append(f"Recent conversation:\n{memory_summary}")
    
    if data_action and data:
        clean_data = _humanize_evidence(data)
        parts.append(f"Here is the data to base your answer on:\n{_evidence_json(clean_data)}")
        
        if data.get("grain") == "day" and data.get("periods") == []:
            parts.append(
                "Note: no daily records exist for this date range. "
                "Do not present monthly totals as if they were daily figures."
            )
    elif data_action and not data:
        parts.append("The query ran but returned no results.")
    else:
        parts.append("No data was retrieved for this question.")
    
    if data_gap_description and data_gap_description != "None.":
        parts.append(f"Limitation: {data_gap_description}")
    
    parts.append(f"The user asked: {user_message}")
    
    return "\n\n".join(parts)
```

**Fix 3: Strengthen the system prompt with concrete examples.**

Replace `SYSTEM_CONTEXT` in `prompts.py`:

```python
SYSTEM_CONTEXT = """
You are the GWSA GeoAnalytics assistant. You help Goodwill of San Antonio staff
understand store performance through natural conversation.

TONE: Write like a smart colleague explaining data over coffee. Lead with the
answer, then add context. Keep it short unless the question is complex.

GOOD examples:
- "Culebra edged out Fredericksburg by about 1,400 visits over the last month — 24,811 to 23,433. Pretty close race."
- "Potranco Rd had its best day on February 14th, pulling in $18,742 in core sales."
- "Revenue is up 8% from February to March across the network."

BAD examples (never do this):
- "Leader: Culebra Retail Store ✅"
- "- Culebra Retail Store: 24,811 doors"
- "Value: $372,761.05"
- "Data grain: daily"
- "What's available: - February 2026 revenue ranking by location"
- "What's missing: - Daily sales data"
- Any bullet-point list of facts. Weave numbers into sentences instead.

RULES:
1. Only state facts from the data provided. Never invent numbers.
2. Use exact values from the data but weave them into natural sentences.
3. If the data only partly answers the question, explain what you can tell
   and what is missing — in a sentence, not a structured list.
4. Never expose SQL, table names, API keys, or internal field names.
5. Never name individual managers.
6. End with 1-2 natural follow-up suggestions when useful.
7. NEVER use bullet points or dashes to list results. Write in flowing paragraphs.
8. NEVER use labels like "Leader:", "Winner:", "Top:", "Value:", "Difference:".
   State the same information in a conversational sentence instead.
"""
```

---

## Problem 3: Slow Responses (8-15 seconds)

### Root cause

Two factors:

**1. Per-store SQL loops.**

`rank_locations()` in `queries.py` calls `_location_metric_total()` once per store (~30 stores = 30 DB round-trips). Even with `ThreadPoolExecutor`, 30 queries × ~200ms each = 2-6 seconds just for retrieval.

**2. Single large LLM call.**

The entire pipeline is synchronous: planner (regex, fast) → retrieval (slow) → one LLM call with a large prompt (system + 6 history turns + full evidence JSON). The LLM call alone takes 3-8 seconds depending on evidence size.

### Fix

**Fix 1: Set-based SQL queries.**

Replace per-store loops with single GROUP BY queries. Example for store revenue ranking:

```sql
-- Instead of 30 separate queries, one query:
SELECT
    loc.LocationID,
    loc.LocationName,
    CAST(SUM(ISNULL(CAST(d.[Revenue] AS DECIMAL(18,4)), 0)) AS DECIMAL(18,2)) AS MetricValue
FROM {total_core_table} AS d
INNER JOIN {locations_table} AS loc
    ON {join_predicate}
WHERE loc.LocationType IN ('Store', 'Outlet')
  AND loc.IsActive = 1
  {category_filter}
  AND CAST(d.[Date] AS DATE) BETWEEN ? AND ?
GROUP BY loc.LocationID, loc.LocationName
ORDER BY MetricValue DESC
OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
```

This turns 30 round-trips into 1.

**Fix 2: Trim the LLM prompt.**

The `_evidence_json()` function sends the full evidence payload including source metadata, timeframe objects, scope labels, and sometimes hundreds of series data points. Most of this is not needed for the answer.

Add aggressive trimming:

```python
_MAX_EVIDENCE_CHARS = 3000  # Hard cap on evidence size

def _trim_for_llm(data: dict) -> dict:
    """Keep only the fields the LLM needs to compose an answer."""
    if not isinstance(data, dict):
        return data
    
    # Remove fields the LLM should never mention
    drop_keys = {"source", "intent", "grain", "scope", "sql_used"}
    out = {k: v for k, v in data.items() if k not in drop_keys}
    
    # Truncate long series
    for key in ("series", "periods", "locations", "rows", "top_store_days"):
        if key in out and isinstance(out[key], list) and len(out[key]) > 10:
            out[key] = out[key][:10]
            out[f"_{key}_note"] = f"Showing top 10 of {len(data[key])} total"
    
    return out
```

**Fix 3: Reduce history in the prompt.**

Change `build_azure_messages()` from 6 history turns to 3:

```python
for item in history[-3:]:  # was history[-6:]
```

---

## Problem 4: Memory Doesn't Work

### Root cause

`memory.py` has one function:

```python
def summarize_history(history: list, max_turns: int = 6) -> str:
    lines = []
    for item in history[-max_turns:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(no prior turns in this session summary)"
```

This does not extract or track anything. It just joins recent messages into a string. The assistant cannot:
- Remember which store was selected
- Carry forward a metric from the previous question
- Carry forward a timeframe
- Resolve "it", "that store", "same thing"

### Fix

Add session state tracking. The frontend already sends `conversation_history` — use it:

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SessionState:
    last_store: Optional[str] = None
    last_store_name: Optional[str] = None
    last_metric: Optional[str] = None
    last_timeframe: Optional[dict] = None
    last_intent: Optional[str] = None

def extract_session_state(history: list, current_plan: dict = None) -> SessionState:
    """Build session state from conversation history."""
    state = SessionState()
    
    # Walk history backwards to find the most recent context
    for msg in reversed(history):
        if msg.get("role") != "assistant":
            continue
        # The assistant's prior responses contain plan metadata
        # (this requires storing plan metadata in history, see chat.py fix)
        meta = msg.get("_plan_meta")
        if meta:
            if not state.last_store and meta.get("store_names"):
                state.last_store_name = meta["store_names"][0]
            if not state.last_metric and meta.get("metric"):
                state.last_metric = meta["metric"]
            if not state.last_timeframe and meta.get("timeframe"):
                state.last_timeframe = meta["timeframe"]
            if not state.last_intent and meta.get("intent"):
                state.last_intent = meta["intent"]
    
    # Override with current plan if available
    if current_plan:
        if current_plan.get("store_names"):
            state.last_store_name = current_plan["store_names"][0]
        if current_plan.get("metric"):
            state.last_metric = current_plan["metric"]
        if current_plan.get("timeframe"):
            state.last_timeframe = current_plan["timeframe"]
        state.last_intent = current_plan.get("intent")
    
    return state

def resolve_references(user_message: str, state: SessionState, store_context: str) -> str:
    """Expand implicit references using session state."""
    text = user_message.lower()
    
    # "What about door count?" → carry forward store + timeframe, swap metric
    if text.startswith("what about") and state.last_store_name:
        return user_message  # planner will detect new metric, router uses last store
    
    # "This store" / "selected store" → use map context
    if ("this store" in text or "selected store" in text) and store_context:
        return user_message.replace("this store", store_context).replace("selected store", store_context)
    
    return user_message

def build_memory_context(state: SessionState, history: list, max_turns: int = 4) -> str:
    """Compact context for the composer prompt."""
    lines = []
    if state.last_store_name:
        lines.append(f"Previously discussed store: {state.last_store_name}")
    if state.last_metric:
        lines.append(f"Last metric: {state.last_metric}")
    if state.last_timeframe:
        label = state.last_timeframe.get("label", "")
        if label:
            lines.append(f"Last timeframe: {label}")
    
    for item in history[-max_turns:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content[:200]}")
    
    return "\n".join(lines) if lines else "(new conversation)"
```

---

## Problem 5: The Regex Planner Cannot Be Fixed

### Why

The problems above show that regex intent classification breaks on:
- Location names containing "store" (Potranco Rd Retail **Store**)
- Questions phrased differently from expected ("on which day did X have" vs "which day had")
- Compound questions ("highest sale per day for February" = daily grain, not monthly)
- Ambiguous metric references ("income" = revenue or net income?)
- Implicit references ("what about door count?" = carry forward everything else)

Every fix creates a new edge case. The regex approach has hit its ceiling.

### The LLM planner fix

Replace the regex planner with a single GPT-5.4-mini call that uses structured output. This is the core V3 change.

```python
import json
from config import Config

PLANNER_SYSTEM_PROMPT = """You classify analytics questions for a Goodwill retail dashboard.
Given a user question and optional context, output a JSON plan. Do NOT answer the question.

METRICS (use these exact names):
- revenue: sales, sale value, core sales, total revenue, net revenue
- door_count: door count, visits, visitors, traffic, foot traffic
- net_income: net income, profit, bottom line
- operating_expenses: expenses, opex, operating expenses
- personnel_expenses: payroll, labor, staffing
- expense_ratio: cost ratio, expense percent
- revenue_per_visit: revenue per visitor, sales per visit

DATA SOURCES:
- Daily revenue (specific dates, "per day", "which day"): TotalCoreTableFinal
- Monthly financials (named months, quarters, YTD): RetailStoreMonthlyFinancialSummary
- Door count (always daily): PeopleCounter
- IMPORTANT: "highest sale per day" or "which day" = DAILY grain → TotalCoreTableFinal
- IMPORTANT: net_income, operating_expenses, personnel_expenses, expense_ratio = MONTHLY ONLY

INTENTS:
- location_summary: general "how is [store] doing"
- compare_locations: compare 2 stores
- rank_locations: rank stores by metric
- rank_time_periods: rank days/dates by metric (NOT stores)
- peak_store_daily_revenue: which store had best single-day revenue
- trend_summary: metric trend over months
- metric_breakdown: break metric down by store
- multi_metric_summary: multiple metrics for one store
- compare_periods: compare two time periods
- correlation_check: do two metrics track together
- derived_metric: computed metric like revenue per visit
- data_catalog: what data is available
- unsupported: can't answer (HR, personnel names, external data)

CRITICAL RULES:
- "On which day did [store] have the highest sale" → intent is rank_time_periods with locations=[store name], NOT rank_locations
- "Which store had the highest sale per day" → intent is peak_store_daily_revenue
- "highest", "best", "top" + "day"/"date" → rank_time_periods (ranking dates, not stores)
- Store names in the question (like "Potranco Rd Retail Store") are location references, not part of the intent pattern
- If no timeframe mentioned, set timeframe to null
- "sale" and "sales" = revenue metric

OUTPUT FORMAT (strict JSON, no other text):
{
  "intent": "string",
  "metrics": ["string"],
  "grain": "day|month|period",
  "scope": "location|all_retail_stores|all_locations",
  "locations": ["store names mentioned"],
  "timeframe_type": "named_month|this_month|last_month|last_n_days|ytd|quarter|null",
  "timeframe_month": "January|February|...|null",
  "timeframe_year": 2026,
  "limit": 5,
  "sort": "desc"
}"""

PLANNER_EXAMPLES = [
    {
        "q": "On which date/day in February did Potranco Rd Retail Store had the highest sale?",
        "a": '{"intent":"rank_time_periods","metrics":["revenue"],"grain":"day","scope":"location","locations":["Potranco Rd Retail Store"],"timeframe_type":"named_month","timeframe_month":"February","timeframe_year":2026,"limit":1,"sort":"desc"}'
    },
    {
        "q": "Compare door counts for Fredericksburg vs Culebra",
        "a": '{"intent":"compare_locations","metrics":["door_count"],"grain":"period","scope":"location","locations":["Fredericksburg","Culebra"],"timeframe_type":"last_month","timeframe_month":null,"timeframe_year":null,"limit":null,"sort":"desc"}'
    },
    {
        "q": "What store had the highest sale per day for February and how much was it?",
        "a": '{"intent":"peak_store_daily_revenue","metrics":["revenue"],"grain":"day","scope":"all_retail_stores","locations":[],"timeframe_type":"named_month","timeframe_month":"February","timeframe_year":2026,"limit":1,"sort":"desc"}'
    },
    {
        "q": "How is Bandera doing this month?",
        "a": '{"intent":"multi_metric_summary","metrics":["revenue","door_count","net_income","operating_expenses"],"grain":"month","scope":"location","locations":["Bandera"],"timeframe_type":"this_month","timeframe_month":null,"timeframe_year":null,"limit":null,"sort":"desc"}'
    },
    {
        "q": "Top 5 stores by revenue in March",
        "a": '{"intent":"rank_locations","metrics":["revenue"],"grain":"period","scope":"all_retail_stores","locations":[],"timeframe_type":"named_month","timeframe_month":"March","timeframe_year":2026,"limit":5,"sort":"desc"}'
    },
    {
        "q": "Is revenue up or down from last month?",
        "a": '{"intent":"compare_periods","metrics":["revenue"],"grain":"month","scope":"all_retail_stores","locations":[],"timeframe_type":"this_month","timeframe_month":null,"timeframe_year":null,"limit":null,"sort":"desc"}'
    },
    {
        "q": "Who manages Blanco?",
        "a": '{"intent":"unsupported","metrics":[],"grain":null,"scope":null,"locations":["Blanco"],"timeframe_type":null,"timeframe_month":null,"timeframe_year":null,"limit":null,"sort":null}'
    },
]


async def plan_request_llm(user_message: str, store_context: str, history: list) -> dict:
    """LLM-based planner using GPT-5.4-mini structured output."""
    
    # Build few-shot messages
    messages = [{"role": "system", "content": PLANNER_SYSTEM_PROMPT}]
    for ex in PLANNER_EXAMPLES:
        messages.append({"role": "user", "content": ex["q"]})
        messages.append({"role": "assistant", "content": ex["a"]})
    
    # Add context if available
    context = ""
    if store_context:
        context = f"[Dashboard shows: {store_context}] "
    messages.append({"role": "user", "content": f"{context}{user_message}"})
    
    client = get_azure_openai_client()
    response = client.chat.completions.create(
        model=Config.AZURE_OPENAI_DEPLOYMENT,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=300,
        timeout=3,
    )
    
    raw = json.loads(response.choices[0].message.content)
    
    # Resolve timeframe to concrete dates
    raw["timeframe"] = resolve_timeframe_from_plan(raw)
    
    # Resolve store names to IDs
    from db.queries import get_location_catalog
    catalog = get_location_catalog(limit=60)
    raw["store_names"] = match_store_names_fuzzy(raw.get("locations", []), catalog)
    
    # Map to V1-compatible plan format for router compatibility
    return normalize_llm_plan(raw)
```

**Fallback to regex when LLM fails:**

```python
def plan_request(user_message: str, store_context: str, history: list = None) -> dict:
    """Try LLM planner first, fall back to regex heuristics."""
    try:
        return plan_request_llm(user_message, store_context, history or [])
    except Exception:
        # V1 regex planner as fallback
        return plan_request_heuristic(user_message, store_context, history)
```

---

## Problem 6: Evidence Format Encourages Robotic Output

### Root cause

The evidence payload from retrieval functions uses machine-oriented field names:

```json
{
  "metric": "door_count",
  "timeframe": {"start": "2026-04-08", "end": "2026-05-07"},
  "locations": [
    {"location_id": "15", "location_name": "Culebra Retail Store", "metric_value": 24811},
    {"location_id": "12", "location_name": "Fredericksburg Retail Store", "metric_value": 23433}
  ],
  "leader": {"location_id": "15", "location_name": "Culebra Retail Store", "metric_value": 24811}
}
```

The LLM sees `leader`, `metric_value`, `location_name` and mirrors them as "Leader:", "Value:", formatted lists.

### Fix

Transform the evidence into natural language BEFORE sending it to the LLM. Instead of sending raw JSON, send a pre-composed evidence summary:

```python
def evidence_to_natural_language(data_action: str, data: dict) -> str:
    """Convert structured evidence into plain English the LLM can narrate from."""
    if not data or not data_action:
        return "No data was retrieved."
    
    if data_action.startswith("compare_locations:"):
        locs = data.get("locations", [])
        metric = data.get("metric", "revenue").replace("_", " ")
        tf = data.get("timeframe", {})
        period = tf.get("label", f"{tf.get('start', '')} to {tf.get('end', '')}")
        
        if len(locs) >= 2:
            a, b = locs[0], locs[1]
            return (
                f"Comparison for {metric} during {period}:\n"
                f"  {a.get('location_name')}: {a.get('metric_value'):,}\n"
                f"  {b.get('location_name')}: {b.get('metric_value'):,}\n"
                f"The first store listed has the higher value."
            )
    
    if data_action.startswith("rank_locations:"):
        locs = data.get("locations", [])
        metric = data.get("metric", "revenue").replace("_", " ")
        tf = data.get("timeframe", {})
        period = tf.get("label", f"{tf.get('start', '')} to {tf.get('end', '')}")
        
        lines = [f"Stores ranked by {metric} for {period}:"]
        for i, loc in enumerate(locs, 1):
            lines.append(f"  #{i} {loc.get('location_name')}: {loc.get('metric_value'):,}")
        return "\n".join(lines)
    
    if data_action.startswith("rank_periods:"):
        periods = data.get("periods", [])
        metric = data.get("metric", "revenue").replace("_", " ")
        tf = data.get("timeframe", {})
        period = tf.get("label", "")
        
        if periods:
            lines = [f"Days ranked by {metric} in {period}:"]
            for i, p in enumerate(periods, 1):
                lines.append(f"  #{i} {p.get('date')}: ${p.get('metric_value'):,.2f}")
            return "\n".join(lines)
        return f"No daily records found for {metric} in {period}."
    
    if data_action == "peak_store_daily_revenue":
        top = data.get("top_store_days", [])
        tf = data.get("timeframe", {})
        period = tf.get("label", "")
        
        if top:
            best = top[0]
            return (
                f"Best single-store day for revenue in {period}:\n"
                f"  {best.get('location_name')} on {best.get('date')}: ${best.get('metric_value'):,.2f}"
            )
        return f"No daily revenue records found for {period}."
    
    # Default: send trimmed JSON (for intents without a custom formatter)
    return json.dumps(
        _trim_for_llm(_humanize_evidence(data)),
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
```

Then in `build_response_prompt()`:

```python
if data_action and data:
    evidence_text = evidence_to_natural_language(data_action, data)
    parts.append(f"Here is the data:\n{evidence_text}")
```

This is the single highest-impact change for tone. When the LLM sees "Culebra Retail Store: 24,811" as plain text instead of `{"leader": {"location_name": "Culebra", "metric_value": 24811}}`, it naturally writes conversational sentences instead of mirroring JSON structure.

---

## Implementation Priority

Do these in order. Each one is independently deployable and testable.

### Week 1: Tone Fixes (Problems 2 + 6)

1. Add `_humanize_evidence()` to `composer.py`
2. Add `evidence_to_natural_language()` to `composer.py`
3. Rewrite `build_response_prompt()` to use natural language evidence
4. Replace `SYSTEM_CONTEXT` in `prompts.py` with the strengthened version (with good/bad examples)
5. Reduce history from 6 turns to 3 in `build_azure_messages()`

**Test**: "Compare door counts for Fredericksburg vs Culebra" should never output "Leader:" or bullet points.

### Week 2: Daily Data Fix (Problem 1)

1. Fix `wants_rank_time_periods()` guard to not block on location names containing "store"
2. Add `wants_store_best_day()` intent detector
3. Add the new intent to `plan_request()` decision cascade
4. Test with all three screenshot questions

**Test**: "On which day in February did Potranco Rd have the highest sale?" should return an actual date and dollar amount.

### Week 3: Performance (Problem 3)

1. Add set-based SQL queries for `rank_locations`, `rank_revenue_days`, `peak_store_daily_revenue`
2. Add `_trim_for_llm()` to cap evidence size
3. Benchmark before/after response times

**Test**: "Top 5 stores by revenue in March" should respond in under 5 seconds.

### Week 4: LLM Planner (Problem 5)

1. Implement `plan_request_llm()` with few-shot examples
2. Wire it as primary planner with regex fallback
3. Add the 7 few-shot examples covering all failure cases
4. Test with the full acceptance question list

**Test**: Any phrasing of "which day did [store] have the highest sale" should work.

### Week 5: Memory (Problem 4)

1. Add `SessionState` dataclass
2. Add `extract_session_state()` and `resolve_references()`
3. Wire into `chat.py` before `plan_request()`
4. Test follow-up questions ("What about door count?")

---

## Acceptance Tests (Screenshot Regression)

These three questions must pass before V3 is considered done:

| # | Question | V1 Result | Required V3 Result |
|---|---|---|---|
| 1 | "On which date/day in February did Potranco Rd Retail Store had the highest sale?" | "I'd need daily transaction data" | Actual date + dollar amount from TotalCoreTableFinal |
| 2 | "On which day/did in February did Potranco Rd Retail store had the highest sale?" | Same failure | Same correct answer (handles typos) |
| 3 | "Compare door counts for Fredericksburg vs Culebra" | "Leader: Culebra Retail Store ✅" with bullet points | Conversational paragraph, no "Leader:", no bullets |

### Tone Validation Rules

Every response must pass ALL of these:

1. Contains zero instances of: "Leader:", "Value:", "Data grain:", "Data Action:", "Retrieved evidence:", "What's available:", "What's missing:"
2. Contains zero bullet-point lists (no lines starting with "- ")
3. Contains no raw JSON field names: "metric_value", "location_name", "location_id"
4. Contains no SQL table names: "TotalCoreTableFinal", "RetailStoreMonthlyFinancialSummary", "PCounter"
5. Reads like a sentence a colleague would say out loud
