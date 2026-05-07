"""Validate LLM planner JSON, resolve timeframes and locations, convert to execution plan."""
from __future__ import annotations

import json
import re
from calendar import monthrange
from datetime import date, timedelta
from typing import Any, List, Optional, Tuple

from ai.schemas import (
    ALLOWED_PLAN_INTENTS,
    CANONICAL_METRICS,
    INTENT_TO_ACTION,
    MONTH_NAMES,
)
from ai.memory import SessionState
from ai.planner_heuristic import infer_trend_months, resolve_trend_reference


QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}


def _month_name_to_num(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    key = raw.strip().lower()[:3]
    if key == "may":
        key = "may"
    return MONTH_NAMES.get(key)


def resolve_quarter(quarter_num: int, year: int) -> dict:
    start_month, end_month = QUARTER_MONTHS[quarter_num]
    last_day = monthrange(year, end_month)[1]
    return {
        "start": date(year, start_month, 1).isoformat(),
        "end": date(year, end_month, last_day).isoformat(),
        "label": f"Q{quarter_num} {year}",
    }


def _last_complete_quarter(today: date) -> Tuple[int, int]:
    """Return (quarter 1-4, year) for the quarter before the one containing today."""
    m, y = today.month, today.year
    if m <= 3:
        return 4, y - 1
    if m <= 6:
        return 1, y
    if m <= 9:
        return 2, y
    return 3, y


def resolve_timeframe_object(
    tf: Optional[dict],
    today: Optional[date] = None,
    default_year: Optional[int] = None,
) -> Optional[dict]:
    """Turn planner timeframe object into {start, end, label}."""
    if not tf or not isinstance(tf, dict):
        return None
    current = today or date.today()
    typ = str(tf.get("type") or "").strip().lower()
    year_hint = tf.get("year")
    try:
        y_int = int(year_hint) if year_hint is not None else None
    except (TypeError, ValueError):
        y_int = None
    if default_year is None:
        default_year = current.year

    if typ in ("named_month", "month"):
        mn = _month_name_to_num(str(tf.get("month_name") or ""))
        if not mn:
            return None
        y = y_int or default_year
        if mn > current.month and y == current.year:
            y = current.year - 1
        last = monthrange(y, mn)[1]
        lab = date(y, mn, 1).strftime("%B %Y")
        return {"start": date(y, mn, 1).isoformat(), "end": date(y, mn, last).isoformat(), "label": lab}

    if typ in ("this_month", "current_month"):
        start = date(current.year, current.month, 1)
        return {
            "start": start.isoformat(),
            "end": current.isoformat(),
            "label": "this month",
        }

    if typ in ("last_month", "previous_month"):
        first_this = date(current.year, current.month, 1)
        last_prev = first_this - timedelta(days=1)
        last_d = monthrange(last_prev.year, last_prev.month)[1]
        lab = last_prev.strftime("%B %Y")
        return {
            "start": date(last_prev.year, last_prev.month, 1).isoformat(),
            "end": date(last_prev.year, last_prev.month, last_d).isoformat(),
            "label": lab,
        }

    if typ == "last_n_days":
        try:
            n = max(1, int(tf.get("n_days") or 30))
        except (TypeError, ValueError):
            n = 30
        start = current - timedelta(days=n - 1)
        return {
            "start": start.isoformat(),
            "end": current.isoformat(),
            "label": f"last {n} days",
        }

    if typ in ("ytd", "this_year", "year_to_date"):
        return {
            "start": date(current.year, 1, 1).isoformat(),
            "end": current.isoformat(),
            "label": f"{current.year} year to date",
        }

    if typ == "last_year":
        y = current.year - 1
        return {
            "start": date(y, 1, 1).isoformat(),
            "end": date(y, 12, 31).isoformat(),
            "label": str(y),
        }

    if typ == "full_year":
        y = y_int or current.year
        return {
            "start": date(y, 1, 1).isoformat(),
            "end": date(y, 12, 31).isoformat(),
            "label": str(y),
        }

    if typ in ("quarter", "named_quarter"):
        try:
            q = int(tf.get("quarter") or tf.get("q") or 0)
        except (TypeError, ValueError):
            q = 0
        if q not in (1, 2, 3, 4):
            qn, yr = _parse_quarter_phrase(tf, current)
            if qn:
                q, y = qn, yr
            else:
                return None
        else:
            y = y_int or current.year
        return resolve_quarter(q, y)

    if typ == "last_quarter":
        q, y = _last_complete_quarter(current)
        return resolve_quarter(q, y)

    if typ == "custom":
        s = tf.get("start")
        e = tf.get("end")
        if not s or not e:
            return None
        return {"start": str(s)[:10], "end": str(e)[:10], "label": "custom range"}

    if typ == "last_week":
        start = current - timedelta(days=current.weekday() + 7)
        end = start + timedelta(days=6)
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": "last week",
        }

    return None


def _parse_quarter_phrase(tf: dict, today: date) -> Tuple[Optional[int], int]:
    """Best-effort parse Q1 / first quarter from freeform fields."""
    text = f"{tf.get('label', '')} {tf.get('month_name', '')}".lower()
    m = re.search(r"\bq([1-4])\b", text)
    q = int(m.group(1)) if m else None
    ym = re.search(r"(20\d{2})", text)
    y = int(ym.group(1)) if ym else today.year
    return q, y


def _fuzzy_match_catalog_names(needles: List[str], catalog: List[dict]) -> List[str]:
    out: List[str] = []
    for raw in needles:
        n = (raw or "").strip()
        if not n:
            continue
        n_low = n.lower()
        best = None
        for loc in catalog:
            name = str(loc.get("name", "")).strip()
            if not name:
                continue
            nl = name.lower()
            if nl == n_low or n_low in nl or nl in n_low:
                best = name
                break
            norm = re.sub(
                r"\s+retail store|\s+donation station|\s+store|\s+station",
                "",
                nl,
            ).strip()
            if norm and (norm in n_low or n_low in norm):
                best = name
                break
        if best and best not in out:
            out.append(best)
    return out[:4]


def normalize_metric_list(metrics: Any) -> List[str]:
    if not metrics:
        return ["revenue"]
    if isinstance(metrics, str):
        raw = [metrics]
    else:
        raw = list(metrics)
    out: List[str] = []
    for m in raw:
        s = str(m).strip().lower()
        if s in CANONICAL_METRICS:
            out.append(s)
    if not out:
        return ["revenue"]
    return out


def convert_llm_plan_to_execution_plan(
    raw: dict,
    session: SessionState,
    store_context: Optional[str],
    catalog: List[dict],
) -> dict:
    """
    Convert validated LLM JSON into the dict shape expected by db.analytics_actions.execute_approved_action.
    """
    intent = str(raw.get("intent") or "unsupported").strip()
    if intent not in ALLOWED_PLAN_INTENTS:
        intent = "unsupported"

    metrics = normalize_metric_list(raw.get("metrics"))
    metric = metrics[0]
    if intent == "multi_metric_summary":
        metric = "revenue"

    timeframe = resolve_timeframe_object(raw.get("timeframe"))
    timeframe_b = resolve_timeframe_object(raw.get("timeframe_b"))

    comparison_payload = None
    if intent == "compare_periods" and timeframe and timeframe_b:
        comparison_payload = {"timeframe_a": timeframe, "timeframe_b": timeframe_b}

    locs = raw.get("locations")
    if isinstance(locs, str):
        locs = [locs]
    store_names = _fuzzy_match_catalog_names(list(locs or []), catalog)

    grain = raw.get("grain") or "auto"
    scope = raw.get("scope") or "all_retail_stores"

    use_viewing_store = bool(
        session.selected_store
        and not store_names
        and intent in ("compare_locations", "multi_metric_summary", "location_summary")
    )

    limit_raw = raw.get("limit")
    try:
        limit_val = int(limit_raw) if limit_raw is not None else 5
    except (TypeError, ValueError):
        limit_val = 5
    limit_val = max(1, min(limit_val, 25))
    if intent == "peak_store_daily_revenue" and (raw.get("limit") in (None, 0)):
        limit_val = max(limit_val, 1)

    trend_months = infer_trend_months(str(raw.get("_user_text") or ""))

    text_for_heuristic = str(raw.get("_user_text") or "")
    use_vs = bool(store_context) and any(
        x in text_for_heuristic.lower()
        for x in ("this store", "selected store", "viewing", "here")
    )
    trend_ref, trend_kind = resolve_trend_reference(store_names, use_vs, store_context)

    action = INTENT_TO_ACTION.get(intent, "none")

    return {
        "intent": intent,
        "action": action,
        "metric": metric,
        "grain": grain,
        "scope": scope,
        "store_names": store_names,
        "use_viewing_store": use_viewing_store,
        "limit": limit_val,
        "timeframe": timeframe,
        "trend_months": trend_months,
        "trend_store_ref": trend_ref,
        "trend_store_ref_kind": trend_kind,
        "comparison": comparison_payload,
        "plan_confidence": raw.get("confidence") or "medium",
        "requires_chart": bool(raw.get("requires_chart")),
        "sort_direction": raw.get("sort_direction") or "desc",
        "_llm_metrics": metrics,
    }


def validate_and_resolve_llm_json(
    parsed: dict,
    session: SessionState,
    store_context: Optional[str],
    catalog: List[dict],
    user_text: str,
) -> Tuple[dict, Optional[str]]:
    """
    Returns (execution_plan, clarification_message_or_None).
    """
    if not isinstance(parsed, dict):
        raise ValueError("plan_not_object")
    parsed = dict(parsed)
    parsed["_user_text"] = user_text

    intent = str(parsed.get("intent") or "").strip()
    if intent not in ALLOWED_PLAN_INTENTS:
        parsed["intent"] = "unsupported"

    if parsed.get("confidence") == "low" and intent not in ("unsupported", "greeting"):
        return (
            {
                "intent": "clarification_needed",
                "action": "none",
                "metric": "revenue",
                "grain": "auto",
                "scope": "all_retail_stores",
                "store_names": [],
                "use_viewing_store": False,
                "limit": 5,
                "timeframe": None,
                "trend_months": 12,
                "trend_store_ref": None,
                "trend_store_ref_kind": None,
                "comparison": None,
                "plan_confidence": "low",
                "requires_chart": False,
                "sort_direction": "desc",
            },
            "Your question looks ambiguous; try naming a month (for example March 2026) "
            "or a specific store.",
        )

    # Performance => multi-metric (handled by intent from LLM)
    exec_plan = convert_llm_plan_to_execution_plan(parsed, session, store_context, catalog)

    # Copy comparison from heuristic if LLM missed pairing — only when both timeframes resolved
    if (
        exec_plan["intent"] == "compare_periods"
        and not exec_plan.get("comparison")
        and exec_plan.get("timeframe")
    ):
        # LLM may have embedded vs in single timeframe — already failed; leave as data gap later
        pass

    return exec_plan, None


def parse_json_content(content: str) -> dict:
    """Strip markdown fences and parse JSON object."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)
