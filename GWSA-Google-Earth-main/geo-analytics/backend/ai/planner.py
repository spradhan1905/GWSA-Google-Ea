"""Parse user text into a typed analytics plan (no LLM, no SQL)."""
import re
from calendar import monthrange
from datetime import date, timedelta
from typing import Optional

from ai.schemas import (
    COMPARE_HINTS,
    MONTH_NAMES,
    RANK_HINTS,
    SUMMARY_HINTS,
)

_MONTH_NAMES_PATTERN = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)


def match_store_names(user_message: str, catalog: list) -> list:
    """Resolve up to two location names directly from the user message."""
    text = (user_message or "").lower()
    matches = []
    for loc in catalog:
        name = str(loc.get("name", "")).strip()
        if not name:
            continue
        name_lc = name.lower()
        normalized = re.sub(
            r"\s+retail store|\s+donation station|\s+store|\s+station",
            "",
            name_lc,
        ).strip()
        if name_lc in text or (normalized and normalized in text):
            if name not in matches:
                matches.append(name)
        if len(matches) >= 2:
            break
    return matches


def _month_num_from_word(raw_month: str) -> int:
    key = raw_month[:3] if raw_month.lower() != "may" else "may"
    return MONTH_NAMES[key]


def _month_window_tf(year: int, month_num: int, label: str) -> dict:
    last = monthrange(year, month_num)[1]
    return {
        "start": date(year, month_num, 1).isoformat(),
        "end": date(year, month_num, last).isoformat(),
        "label": label or date(year, month_num, 1).strftime("%B %Y"),
    }


def infer_scope(user_message: str) -> str:
    t = (user_message or "").lower()
    if "all location" in t or "every location" in t or "whole network" in t:
        return "all_locations"
    return "all_retail_stores"


def infer_trend_months(text: str) -> int:
    t = text.lower()
    m = re.search(r"\b(\d{1,2})\s*(?:-|–)?\s*(?:month|months)\b", t)
    if m:
        return max(1, min(int(m.group(1)), 36))
    if re.search(r"\b(one|a)\s+year\b", t) or re.search(r"\b12\s*(month|months)\b", t):
        return 12
    if "two year" in t or "2 year" in t:
        return 24
    return 12


def parse_comparison_timeframes(user_message: str, today: date = None):
    """Return dict with timeframe_a/b or None."""
    current_day = today or date.today()
    text = (user_message or "").strip().lower()

    preset = re.search(
        r"\b(this\s+month|current\s+month)\b\s*(?:vs\.?|versus)\b\s*\b(last\s+month|previous\s+month)\b",
        text,
    ) or re.search(
        r"\b(last\s+month|previous\s+month)\b\s*(?:vs\.?|versus)\b\s*\b(this\s+month|current\s+month)\b",
        text,
    )
    if preset:
        def _this_month():
            return {
                "start": date(current_day.year, current_day.month, 1).isoformat(),
                "end": current_day.isoformat(),
                "label": "this month",
            }

        def _last_month():
            first_this = date(current_day.year, current_day.month, 1)
            last_prev = first_this - timedelta(days=1)
            return _month_window_tf(last_prev.year, last_prev.month, last_prev.strftime("%B %Y"))

        g1, g2 = preset.group(1), preset.group(2)
        if "this" in g1 or "current" in g1:
            return {"timeframe_a": _this_month(), "timeframe_b": _last_month()}
        return {"timeframe_a": _last_month(), "timeframe_b": _this_month()}

    m = re.search(
        rf"\b({_MONTH_NAMES_PATTERN})(?:\s+(20\d{{2}}))?\s*"
        r"(?:vs\.?|versus|compared\s+to|compared\s+with)\s*"
        rf"\b({_MONTH_NAMES_PATTERN})(?:\s+(20\d{{2}}))?",
        text,
        re.I,
    )
    if not m:
        return None

    raw_a, year_a_g, raw_b, year_b_g = m.group(1), m.group(2), m.group(3), m.group(4)
    ma = _month_num_from_word(raw_a)
    mb = _month_num_from_word(raw_b)
    year_a = int(year_a_g) if year_a_g else None
    year_b = int(year_b_g) if year_b_g else None
    fallback_year = current_day.year
    if ma > current_day.month and mb > current_day.month:
        fallback_year = current_day.year - 1
    y_a = year_a or year_b or fallback_year
    y_b = year_b or year_a or fallback_year

    tfa = _month_window_tf(y_a, ma, "")
    tfa["label"] = date(y_a, ma, 1).strftime("%B %Y")
    tfb = _month_window_tf(y_b, mb, "")
    tfb["label"] = date(y_b, mb, 1).strftime("%B %Y")
    return {"timeframe_a": tfa, "timeframe_b": tfb}


def detect_metric(user_message: str) -> str:
    text = (user_message or "").lower()
    if any(word in text for word in ("door count", "door counts")):
        return "door_count"
    if ("visitor" in text or "traffic" in text or " visits" in text) and (
        "revenue per" not in text and "sale per" not in text and "per visit" not in text and "per visitor" not in text
    ):
        return "door_count"
    if "expense ratio" in text or "cost ratio" in text:
        return "expense_ratio"
    if "payroll" in text or "personnel expense" in text or "staffing expense" in text:
        return "personnel_expenses"
    if "operating expense" in text or "opex" in text or ("expense" in text and "personnel" not in text):
        if "ratio" not in text and "door" not in text:
            return "operating_expenses"
    if "net income" in text or "bottom line" in text or ("profit" in text and "per" not in text):
        return "net_income"
    if any(word in text for word in ("sale value", "sales value", "sales day", "sales days", "highest sale", "total sale", "sale ", "sales ")):
        return "revenue"
    return "revenue"


def wants_data_catalog(text: str) -> bool:
    t = text.lower().strip()
    if not t:
        return False
    return (
        "what data" in t or "what can i ask" in t or "what questions" in t or "capabilities" in t
        or ("help" in t and "assistant" not in t and len(t) < 80)
    )


def wants_trend_summary(text: str) -> bool:
    t = text.lower()
    if "trend" in t:
        return True
    if re.search(r"\b(month|months)\s+of\s+", t) and ("revenue" in t or "income" in t or "door" in t or "performance" in t):
        return True
    return bool(re.search(r"\b(show|historical)\b.*(\d{1,2})\s*(month|months)\b", t))


def wants_correlation(text: str) -> bool:
    t = text.lower()
    has_traffic = any(x in t for x in ("door", "traffic", "visitor", "visitors"))
    has_rev = "revenue" in t or "sales" in t
    return (
        (has_traffic and has_rev and ("track" in t or "tracked" in t or "together" in t or "mean" in t or "relationship" in t))
        or "correlation" in t
        or ("did " in t and "visitor" in t and has_rev)
        or ("more visitor" in t and has_rev)
        or ("busier" in t and has_traffic and has_rev and "revenue" in t)
    )


def wants_derived_revenue_per_visit(text: str) -> bool:
    t = text.lower()
    return "revenue per" in t or "sales per" in t or "per donor visit" in t or ("per visitor" in t or "per visit" in t) and ("revenue" in t or "sales" in t)


def wants_metric_breakdown(text: str) -> bool:
    t = text.lower()
    if "rank" in t and "which store" not in text:
        return False
    if "top " in t and "store" in t:
        return False
    return ("break down" in t or "broken down" in t or ("by store" in t and ("revenue" in t or "sales" in t or "door" in t)))


def wants_map_donor_context(text: str) -> bool:
    t = text.lower()
    return ("donor address" in t or "donor map" in t or "geo" in t and "donor" in t
            or ("where" in t and "donor" in t and "located" in t))


def wants_multi_metric(text: str) -> bool:
    t = text.lower()
    if "performance" in t and ("this month" in t or "march" in t or "february" in t or "month" in t):
        return True
    cues = ["net income", "operating expense", "personnel", "door count", "expense ratio", "traffic"]
    hits = sum(1 for c in cues if c in t)
    return hits >= 2


def wants_rank_time_periods(user_message: str) -> bool:
    """True when the user ranks calendar days/dates rather than stores."""
    t = (user_message or "").strip().lower()
    if not t:
        return False
    if re.search(r"\b(which|what)\s+store\b", t) and not re.search(r"\b(which|what)\s+(day|date)\b", t):
        return False
    if re.search(r"\b(which|what)\s+(day|date)\b", t):
        return True
    if "day and date" in t:
        return True
    if ("busiest" in t or "peak" in t) and ("day" in t or "date" in t):
        return True
    if re.search(r"\btop\s+\d+\s+(days?|sales\s+days?)\b", t):
        return True
    if "sales days" in t or "revenue days" in t:
        return True
    rank_ok = any(hint in t for hint in RANK_HINTS)
    if rank_ok and re.search(r"\b(day|date|daily|calendar)\b", t):
        return True
    return False


def month_window(year: int, month: int, label: str) -> dict:
    last_day = monthrange(year, month)[1]
    return {
        "start": date(year, month, 1).isoformat(),
        "end": date(year, month, last_day).isoformat(),
        "label": label,
    }


def parse_timeframe(user_message: str, today: date = None) -> dict:
    """Resolve common natural-language date ranges without giving SQL access to the model."""
    current_day = today or date.today()
    text = (user_message or "").lower()

    if any(token in text for token in ("this year", "year to date", "ytd")):
        return {
            "start": date(current_day.year, 1, 1).isoformat(),
            "end": current_day.isoformat(),
            "label": f"{current_day.year} year to date",
        }

    if "last year" in text:
        year = current_day.year - 1
        return {
            "start": date(year, 1, 1).isoformat(),
            "end": date(year, 12, 31).isoformat(),
            "label": str(year),
        }

    if "this month" in text or "current month" in text:
        return {
            "start": date(current_day.year, current_day.month, 1).isoformat(),
            "end": current_day.isoformat(),
            "label": "this month",
        }

    if "last month" in text or "previous month" in text:
        first_this_month = date(current_day.year, current_day.month, 1)
        last_prev_month = first_this_month - timedelta(days=1)
        return month_window(
            last_prev_month.year,
            last_prev_month.month,
            last_prev_month.strftime("%B %Y"),
        )

    if "last 30" in text or "past 30" in text:
        return {
            "start": (current_day - timedelta(days=29)).isoformat(),
            "end": current_day.isoformat(),
            "label": "last 30 days",
        }

    month_match = re.search(
        r"\b("
        rf"{_MONTH_NAMES_PATTERN}"
        r")\b(?:\s+(\d{4}))?",
        text,
        re.I,
    )
    if month_match:
        raw_month = month_match.group(1)
        month_num = _month_num_from_word(raw_month)
        explicit_year = month_match.group(2)
        if explicit_year:
            year = int(explicit_year)
        else:
            year = current_day.year if month_num <= current_day.month else current_day.year - 1
        return month_window(year, month_num, date(year, month_num, 1).strftime("%B %Y"))

    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match:
        year = int(year_match.group(1))
        end = current_day if year == current_day.year else date(year, 12, 31)
        return {
            "start": date(year, 1, 1).isoformat(),
            "end": end.isoformat(),
            "label": str(year) if year != current_day.year else f"{year} year to date",
        }

    return None


def resolve_trend_reference(store_names: list, use_viewing_store: bool, store_context: Optional[str]):
    """Return store ref string (name fragment or LocationID context) when the dashboard anchors a query."""
    if store_names:
        return store_names[0], "name"
    if use_viewing_store and store_context:
        return store_context.strip(), "context_explicit"
    if store_context and str(store_context).strip():
        return str(store_context).strip(), "dashboard_context"
    return None, None


def plan_request(user_message: str, store_context: str, _history: list) -> dict:
    """Choose an approved analytics action with local heuristics."""
    from db.queries import get_location_catalog

    catalog = get_location_catalog(limit=60)
    text_raw = user_message or ""
    text = text_raw.lower()

    metric = detect_metric(text_raw)
    timeframe = parse_timeframe(text_raw)
    store_names = match_store_names(text_raw, catalog)
    use_viewing_store = bool(store_context) and any(
        token in text for token in ("this store", "selected store", "viewing", "here")
    )
    scope = infer_scope(text_raw)

    numbers = re.findall(r"\b(\d{1,2})\b", text)
    parsed_limit = int(numbers[0]) if numbers else 5

    action = "none"
    intent = "unsupported"
    grain = "auto"
    trend_months = infer_trend_months(text_raw)
    comparison_payload = parse_comparison_timeframes(text_raw)

    unsupported_manager = ("who manage" in text or "which manager" in text or "store manager named" in text)

    compare_ok = any(hint in text for hint in COMPARE_HINTS) and comparison_payload is None and (
        len(store_names) >= 2 or (len(store_names) == 1 and use_viewing_store)
    )
    rank_ok = any(hint in text for hint in RANK_HINTS)

    if unsupported_manager:
        intent = "unsupported"
        action = "none"

    elif wants_data_catalog(text_raw):
        intent = "data_catalog"
        action = "data_catalog"

    elif comparison_payload:
        intent = "compare_periods"
        action = "compare_periods"

    elif wants_correlation(text_raw) and timeframe:
        intent = "correlation_check"
        action = "correlation_check"

    elif wants_trend_summary(text_raw):
        intent = "trend_summary"
        action = "trend_summary"

    elif wants_derived_revenue_per_visit(text_raw) and timeframe:
        has_focus_store = bool(resolve_trend_reference(store_names, use_viewing_store, store_context)[0])
        network_focus = (
            "each store" in text or "by store" in text or "per store" in text
            or "every store" in text or " all stores" in text
        )
        intent = "derived_metric"
        if has_focus_store and not network_focus:
            action = "revenue_door_series"
        else:
            action = "revenue_per_visit_rank"

    elif wants_multi_metric(text_raw) and timeframe:
        intent = "multi_metric_summary"
        action = "multi_metric_summary"

    elif wants_map_donor_context(text_raw):
        intent = "map_context_summary"
        action = "map_context_summary"

    elif wants_metric_breakdown(text_raw) and timeframe:
        intent = "metric_breakdown"
        action = "metric_breakdown"

    elif compare_ok:
        action = "compare_locations"
        intent = "compare_locations"

    elif wants_rank_time_periods(text_raw):
        intent = "rank_time_periods"
        grain = "day"
        if timeframe:
            action = "rank_time_periods"

    elif rank_ok:
        action = "rank_locations"
        intent = "rank_locations"

    elif len(store_names) == 1 or use_viewing_store or any(hint in text for hint in SUMMARY_HINTS):
        action = "location_summary"
        intent = "location_summary"

    trend_ref, trend_ref_kind = resolve_trend_reference(store_names, use_viewing_store, store_context)

    return {
        "intent": intent,
        "action": action,
        "metric": metric,
        "grain": grain,
        "scope": scope,
        "store_names": [str(name).strip()[:80] for name in store_names[:2] if str(name).strip()],
        "use_viewing_store": use_viewing_store,
        "limit": max(1, min(parsed_limit, 10)),
        "timeframe": timeframe,
        "trend_months": trend_months,
        "trend_store_ref": trend_ref,
        "trend_store_ref_kind": trend_ref_kind,
        "comparison": comparison_payload,
    }
