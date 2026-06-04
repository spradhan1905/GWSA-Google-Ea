"""Template-based follow-up suggestions (V2)."""
from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional

_FOLLOWUP_TEMPLATES = {
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
        "How does {timeframe_label} total revenue compare to the month before?",
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
    "correlation_check": [
        "Break out that relationship by store for the same month",
        "Show daily revenue and traffic for the busiest store that month",
        "Compare this month to the same month last year",
    ],
    "metric_breakdown": [
        "Which single day was strongest in that range?",
        "Show door count ranking for the same period",
        "How does the top store compare to the network median?",
    ],
    "category_breakdown": [
        "Add door count to the comparison",
        "Show the monthly trend for both stores",
        "Compare them on net income for the same period",
    ],
    "derived_metric": [
        "Show the same ranking for raw revenue",
        "Which store improved revenue per visit the most month over month?",
        "Plot revenue and door count together for the leader",
    ],
    "budget_vs_actual": [
        "Which store is furthest below budget?",
        "Show actual vs budget trend for the top store",
        "Compare budget attainment to last month",
    ],
}

_METRIC_LABEL = {
    "revenue": "revenue",
    "door_count": "door count",
    "net_income": "net income",
    "operating_expenses": "operating expenses",
    "personnel_expenses": "personnel expenses",
    "expense_ratio": "expense ratio",
    "revenue_per_visit": "revenue per visit",
    "donations": "donations",
    "budget_attainment": "budget attainment",
}


def _leader_name(data: dict, plan: dict) -> str:
    if not isinstance(data, dict):
        return "the leading store"
    locs = data.get("locations") or []
    if locs:
        return str(locs[0].get("location_name") or "the leading store")
    leader = data.get("leader")
    if isinstance(leader, dict):
        return str(leader.get("location_name") or "the leading store")
    return "the leading store"


def _timeframe_label(data: Optional[dict], plan: dict) -> str:
    tf = (data or {}).get("timeframe") or plan.get("timeframe") or {}
    return str(tf.get("label") or "that period")


def _random_other_store(plan: dict) -> str:
    """Pick a store name different from the one in context (best-effort)."""
    names = plan.get("store_names") or []
    main = str(names[0]).lower() if names else ""
    try:
        from db.queries import get_location_catalog

        cat = get_location_catalog(limit=40)
        pool = [
            str(c.get("name"))
            for c in cat
            if c.get("name") and str(c.get("name")).lower() != main
        ]
        if pool:
            return random.choice(pool)
    except Exception:
        pass
    return "another nearby store"


def build_followups(
    intent: str,
    plan: dict,
    data: Optional[dict],
    *,
    limit: int = 3,
) -> List[str]:
    """Return natural-language follow-up questions (template-filled)."""
    tmpl = _FOLLOWUP_TEMPLATES.get(intent) or _FOLLOWUP_TEMPLATES["rank_locations"]

    metric = str(plan.get("metric") or "revenue")
    mlab = _METRIC_LABEL.get(metric, metric.replace("_", " "))
    tfl = _timeframe_label(data, plan)
    leader = _leader_name(data or {}, plan)
    try:
        cur_l = int(plan.get("limit") or 5)
    except (TypeError, ValueError):
        cur_l = 5
    next_limit = min(cur_l + 3, 10)

    def _sub(s: str) -> str:
        out = s
        out = out.replace("{leader_name}", leader)
        out = out.replace("{metric}", mlab)
        out = out.replace("{timeframe_label}", tfl)
        out = out.replace("{next_limit}", str(next_limit))
        out = out.replace("{primary_metric}", mlab)
        out = re.sub(r"\{random_other_store\}", _random_other_store(plan), out)
        return out

    filled = [_sub(t) for t in tmpl]
    random.shuffle(filled)
    return filled[: max(1, min(limit, 5))]


def chart_config_for_intent(intent: str, metric: str) -> Optional[Dict[str, Any]]:
    """Chart metadata keyed by intent (spec — payload-driven charts)."""
    m = metric or "revenue"
    configs: Dict[str, Dict[str, Any]] = {
        "rank_locations": {"type": "horizontal_bar", "x_key": "metric_value", "y_key": "location_name"},
        "rank_time_periods": {"type": "bar", "x_key": "date", "y_key": "metric_value"},
        "peak_store_daily_revenue": {"type": "bar", "x_key": "location_name", "y_key": "metric_value"},
        "trend_summary": {"type": "line", "x_key": "PeriodMonth", "y_key": "NetRevenue"},
        "compare_locations": {"type": "grouped_bar", "x_key": "location_name", "y_key": "metric_value"},
        "compare_periods": {"type": "grouped_bar", "x_key": "label", "y_key": "value"},
        "correlation_check": {"type": "scatter", "x_key": "network_revenue", "y_key": "network_door_count"},
        "revenue_door_series": {"type": "dual_axis_line", "x_key": "date", "y1_key": "revenue", "y2_key": "door_count"},
        "metric_breakdown": {"type": "horizontal_bar", "x_key": "metric_value", "y_key": "location_name"},
        "derived_metric": {"type": "horizontal_bar", "x_key": "metric_value", "y_key": "location_name"},
        "budget_vs_actual": {"type": "horizontal_bar", "x_key": "attainment_pct", "y_key": "location_name"},
        "category_breakdown": {"type": "bar", "x_key": "category", "y_key": "revenue"},
    }
    base = configs.get(intent)
    if not base:
        return None
    out = dict(base)
    out["y_label"] = m.replace("_", " ").title()
    return out
