"""Standard chat API payloads: success branches, data gaps, provider errors."""
from typing import Optional

from flask import jsonify

from ai.context import data_gap_code, sources_from_payload

_DATA_GAP_PROMPT_TEXT = {
    "timeframe_required": (
        "A calendar period is required (for example a named month or explicit date range)."
    ),
    "no_daily_records_in_range": (
        "The daily ranking query returned no matching days in the retrieved evidence for this range."
    ),
    "store_anchor_required": (
        "Choose a location on the map or type a specific store name in the dashboard context "
        "so retrieval can anchor to LocationID.",
    ),
    "correlation_timeframe_required": (
        "Name a month or explicit date range so daily revenue and door totals can be aligned for correlation.",
    ),
    "unsupported_question": (
        "The question falls outside grounded analytics intents (for example naming individual managers).",
    ),
}


def describe_data_gap(code: str) -> str:
    """Short explanation for the composer prompt."""
    if not code:
        return "None."
    return _DATA_GAP_PROMPT_TEXT.get(code, str(code))


def timeframe_required_gap_body() -> dict:
    return {
        "reply": (
            "Please name a calendar window (for example \"March\", \"March 2025\", or \"last 30 days\") "
            "so I can use the daily sales dataset for day-level questions or peak single-day store sales."
        ),
        "sql_used": None,
        "data": None,
        "sources": [],
        "data_gap": "timeframe_required",
    }


def unsupported_question_body() -> dict:
    return {
        "reply": (
            "I work from the GeoAnalytics data in this app—sales, door traffic, trends, and store comparisons. "
            "I couldn’t map that message to a specific report. Try adding a month or date range, naming stores to compare, "
            "or rephrasing as a single analytics question. (Manager names and other HR details aren’t available here.)"
        ),
        "sql_used": "unsupported",
        "data": {"intent": "unsupported", "reason": "policy_or_unsupported_question"},
        "sources": [],
        "data_gap": "unsupported_question",
    }


def store_anchor_required_gap_body(feature_description: str = "that view") -> dict:
    return {
        "reply": (
            f"I need a specific store to load {feature_description}. "
            "Select a pin on the map or type the full store name in your message."
        ),
        "sql_used": None,
        "data": None,
        "sources": [],
        "data_gap": "store_anchor_required",
    }


def correlation_timeframe_required_gap_body() -> dict:
    return {
        "reply": (
            "To compare network door traffic with revenue day-by-day, please name a month or "
            "date range (for example \"March 2026\" or \"last 30 days\")."
        ),
        "sql_used": None,
        "data": None,
        "sources": [],
        "data_gap": "correlation_timeframe_required",
    }


def quota_fallback_reply(data_action: str, analytics_data: dict) -> str:
    """Plain fallback when AI fails but approved analytics data exists."""
    if not data_action or not analytics_data:
        return (
            "The AI service is temporarily unavailable or has hit its quota limit. "
            "The data request completed, but I could not generate a full AI narrative right now."
        )

    if data_action.startswith("rank_periods:"):
        periods = analytics_data.get("periods") or []
        metric = analytics_data.get("metric", "revenue")
        if periods:
            leader = periods[0]
            return (
                "The AI service is temporarily unavailable; the retrieval ranked calendar days by "
                f"{metric.replace('_', ' ')} — top day **{leader.get('date')}** with "
                f"value **{leader.get('metric_value')}**."
            )
        tf = (analytics_data or {}).get("timeframe") or {}
        lbl = tf.get("label") or ""
        return (
            "The AI service is temporarily unavailable; the daily-period query returned no matching days "
            f"for {metric.replace('_', ' ')}{' in ' + lbl if lbl else ''}."
        )

    if data_action.startswith("rank_locations:"):
        locations = analytics_data.get("locations") or []
        metric = analytics_data.get("metric", "revenue")
        if locations:
            leader = locations[0]
            value = leader.get("metric_value")
            return (
                "The AI service is temporarily unavailable, but based on the approved analytics query, "
                f"{leader.get('location_name')} is currently ranked highest for {metric} "
                f"with a value of {value}."
            )

    if data_action.startswith("compare_locations:"):
        leader = analytics_data.get("leader")
        metric = analytics_data.get("metric", "revenue")
        if leader:
            return (
                "The AI service is temporarily unavailable, but the comparison completed. "
                f"{leader.get('location_name')} leads for {metric} with a value of {leader.get('metric_value')}."
            )

    if data_action == "location_summary":
        metrics = (analytics_data or {}).get("metrics") or {}
        return (
            "The AI service is temporarily unavailable, but the store summary completed. "
            f"This month revenue is {metrics.get('this_month_revenue', 0)}, "
            f"last 30 days door count is {metrics.get('last_30_days_door_count', 0)}, "
            f"and average daily door count is {metrics.get('avg_daily_door_count_30d', 0)}."
        )

    if data_action and data_action.startswith("trend_summary:"):
        rows = (analytics_data or {}).get("rows") or []
        name = (analytics_data or {}).get("location_name") or "selected store"
        if rows:
            latest = rows[-1]
            return (
                "The AI service is temporarily unavailable; KPI trend rows retrieved. "
                f"Latest bucket for {name} shows NetRevenue **{latest.get('NetRevenue')}**, "
                f"DoorCount **{latest.get('DoorCount')}**."
            )

    if data_action and data_action.startswith("compare_periods:"):
        pa = (analytics_data or {}).get("period_a") or {}
        pb = (analytics_data or {}).get("period_b") or {}
        m = (analytics_data or {}).get("metric", "")
        return (
            "The AI service is temporarily unavailable, but period comparison totals were computed "
            f"for {m}: period A={pa.get('value')}, period B={pb.get('value')} "
            f"(pct change vs B: {(analytics_data or {}).get('pct_change_vs_b')})."
        )

    if data_action == "correlation:revenue_door":
        r_val = (analytics_data or {}).get("pearson_r")
        overlap = (analytics_data or {}).get("overlap_days", 0)
        return (
            "The AI service is temporarily unavailable; daily network correlation finished. "
            f"Pearson r={r_val}, overlap_days={overlap}."
        )

    if data_action == "peak_store_daily_revenue":
        leader = (analytics_data or {}).get("leader")
        if leader:
            return (
                "The AI service is temporarily unavailable; peak single-store day query finished "
                f"— **{leader.get('location_name')}** on **{leader.get('date')}**, "
                f"{leader.get('metric_value')} (core revenue)."
            )

    if data_action and data_action.startswith("derived:"):
        locs = (analytics_data or {}).get("locations") or []
        if locs:
            top = locs[0]
            return (
                "The AI service is temporarily unavailable; revenue-per-visit ranking completed. "
                f"Leading store **{top.get('location_name')}** at ${top.get('revenue_per_visit')} per visit."
            )

    if data_action and data_action.startswith("revenue_door_series:"):
        s = (analytics_data or {}).get("series") or []
        loc = (analytics_data or {}).get("location_name") or "store"
        if s:
            last = s[-1]
            return (
                "The AI service is temporarily unavailable; retrieved aligned revenue/traffic rows. "
                f"Latest entry for **{loc}**: date/period keys {last}."
            )

    if data_action and data_action.startswith("multi_metric:"):
        m = ((analytics_data or {}).get("metrics") or {})
        return (
            "The AI service is temporarily unavailable; multi-metric snapshot ready. "
            f"DoorCount total={m.get('door_count_total')}; NetRevenue={m.get('net_revenue')}."
        )

    if data_action.startswith("metric_breakdown:"):
        locs = (analytics_data or {}).get("locations") or []
        if locs:
            top = locs[0]
            return (
                "The AI service is temporarily unavailable; store breakdown fetched. "
                f"Leading **{top.get('location_name')}** metric_value={top.get('metric_value')}."
            )

    if data_action == "data_catalog":
        desc = ((analytics_data or {}).get("description") or "capability overview")[:200]
        return (
            "The AI service is temporarily unavailable; here's the summarized catalog excerpt: "
            f"{desc}..."
        )

    if data_action and data_action.startswith("map_context:"):
        pins = (analytics_data or {}).get("donor_pins_returned_by_query")
        return (
            "The AI service is temporarily unavailable; donor geography query completed. "
            f"Pins returned={pins}."
        )

    if data_action and data_action.startswith("budget_vs_actual"):
        if data_action.startswith("budget_vs_actual:store"):
            att = (analytics_data or {}).get("attainment_pct")
            nm = (analytics_data or {}).get("location_name") or "the store"
            return (
                "The AI service is temporarily unavailable; budget vs actual totals are ready. "
                f"**{nm}**: actual **{(analytics_data or {}).get('actual_revenue')}**, "
                f"budget **{(analytics_data or {}).get('budget_revenue')}**, "
                f"attainment **{att}%**."
            )
        locs = (analytics_data or {}).get("locations") or []
        if locs:
            top = locs[0]
            return (
                "The AI service is temporarily unavailable; store budget ranking is ready. "
                f"Leader **{top.get('location_name')}** at **{top.get('attainment_pct')}%** of budget."
            )

    if data_action and "donations" in (data_action or ""):
        locs = (analytics_data or {}).get("locations") or []
        periods = (analytics_data or {}).get("periods") or []
        if locs:
            top = locs[0]
            return (
                "The AI service is temporarily unavailable; donation ranking completed. "
                f"**{top.get('location_name')}** leads at **{top.get('metric_value')}**."
            )
        if periods:
            best = periods[0]
            return (
                "The AI service is temporarily unavailable; peak donation day: "
                f"**{best.get('date')}** at **{best.get('metric_value')}**."
            )

    return (
        "The AI service is temporarily unavailable or has hit its quota limit. "
        "The approved analytics request completed successfully."
    )


def provider_error_response(exc: Exception, data_action: str, analytics_data: dict):
    """Map AI provider exceptions to Flask (jsonify, status_code)."""
    message = str(exc).strip() or "Unknown AI service error."
    lowered = message.lower()

    if any(token in lowered for token in ("429", "quota", "rate limit", "resource exhausted", "too many requests")):
        body = dict(
            error="Azure OpenAI quota or rate limit reached. Please wait or increase your Azure OpenAI quota.",
            reply=quota_fallback_reply(data_action, analytics_data),
            sql_used=data_action,
            data=analytics_data,
            sources=sources_from_payload(analytics_data),
        )
        dg = data_gap_code({}, data_action, analytics_data)
        if dg:
            body["data_gap"] = dg
        return jsonify(body), 429

    if any(token in lowered for token in ("api key", "permission denied", "permission", "forbidden", "403", "401", "unauthorized")):
        return jsonify(error=f"Azure OpenAI authentication or access error: {message}"), 502

    if any(token in lowered for token in ("timeout", "timed out", "deadline exceeded", "connection", "unavailable", "503")):
        return jsonify(error=f"Azure OpenAI network or availability error: {message}"), 504

    return jsonify(error=f"AI service error: {message}"), 500


def demo_reply(message: str, store_context: str = None) -> str:
    """Provide helpful demo responses when no AI provider is configured."""
    msg = message.lower()
    store = store_context or "the selected location"

    if 'revenue' in msg or 'income' in msg:
        return (
            f"Based on demo data for {store}, this location shows average monthly net revenue of approximately "
            f"$145,000 with a healthy expense ratio around 68%. To see live data, configure Azure OpenAI "
            f"and SQL Server connection."
        )
    if 'door count' in msg or 'visitor' in msg:
        return (
            f"Demo data shows {store} averages about 120 donor visits per day, with weekends seeing up to "
            f"250 visits. Peak hours are typically 10am-2pm on Saturdays."
        )
    if 'compare' in msg or 'best' in msg or 'worst' in msg:
        return (
            "In demo mode, the Fredericksburg Rd location leads with the highest net revenue, while Bandera Rd "
            "shows the strongest growth trend. Connect to your SQL Server for actual comparisons."
        )
    if 'manager' in msg:
        return (
            "GWSA locations are supported by store managers and regional leaders, but this demo does not expose "
            "individual manager names."
        )
    return (
        f"I'm the GWSA GeoAnalytics AI assistant running in demo mode. I can help analyze store performance, "
        f"door counts, revenue trends, and compare locations. Configure Azure OpenAI in backend/.env for full AI "
        f"capabilities. Try asking about revenue, door counts, or store comparisons!"
    )


def chat_success_payload(
    reply: str,
    plan: dict,
    data_action: str,
    analytics_data: dict,
    *,
    session_payload: Optional[dict] = None,
    followups: Optional[list] = None,
    chart: Optional[dict] = None,
    response_type: str = "answer",
    plan_used: Optional[dict] = None,
) -> dict:
    """Normalize JSON body for a successful completion (V2 envelope)."""
    body: dict = {
        "reply": reply,
        "response_type": response_type,
        "sql_used": data_action,
        "data": analytics_data,
        "data_action": (data_action or "").split(":")[0] if data_action else None,
    }
    body["sources"] = sources_from_payload(analytics_data)
    dg = data_gap_code(plan, data_action or "", analytics_data or {})
    if dg:
        body["data_gap"] = dg
    if session_payload is not None:
        body["session_state"] = session_payload
    if followups:
        body["followups"] = followups
    if chart:
        body["chart"] = chart
    if plan_used:
        body["plan_used"] = plan_used
    conf = plan.get("plan_confidence")
    if conf:
        body["confidence"] = conf
    return body
