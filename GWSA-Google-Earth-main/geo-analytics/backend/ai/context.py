"""Evidence helpers: source metadata and data-gap signals."""


def sources_from_payload(analytics_data: dict) -> list:
    """Surface source metadata from structured analytics payloads."""
    if not analytics_data:
        return []
    src = analytics_data.get("source")
    if isinstance(src, dict):
        return [src]
    if isinstance(src, list):
        return [x for x in src if isinstance(x, dict)]
    return []


def data_gap_code(plan: dict, data_action: str, analytics_data: dict):
    if plan.get("intent") in ("rank_time_periods", "peak_store_daily_revenue") and not plan.get("timeframe"):
        return "timeframe_required"
    if data_action and str(data_action).startswith("rank_periods:"):
        if isinstance(analytics_data, dict) and not (analytics_data.get("periods") or []):
            return "no_daily_records_in_range"
    if data_action == "peak_store_daily_revenue" and isinstance(analytics_data, dict):
        if analytics_data.get("leader") is None:
            return "no_daily_records_in_range"
    return None
