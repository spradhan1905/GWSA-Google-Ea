"""Evidence helpers: source metadata, trimming, data-gap signals, chart hints."""

from typing import Optional

_MAX_EVIDENCE_SERIES_POINTS = 120


def trim_evidence(data: dict) -> dict:
    """Trim bulky list fields for LLM prompts (same contract as legacy composer helper)."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    series = out.get("series")
    if isinstance(series, list) and len(series) > _MAX_EVIDENCE_SERIES_POINTS:
        out["series"] = series[:_MAX_EVIDENCE_SERIES_POINTS]
        out["_series_truncated_note"] = (
            f"Only the first {_MAX_EVIDENCE_SERIES_POINTS} calendar points are shown."
        )
    locs = out.get("locations")
    if isinstance(locs, list) and len(locs) > 40:
        out["locations"] = locs[:40]
        out["_locations_truncated_note"] = "Top 40 rows shown."
    periods = out.get("periods")
    if isinstance(periods, list) and len(periods) > 40:
        out["periods"] = periods[:40]
    return out


def chart_rows_for_payload(intent: str, analytics_data: dict) -> list:
    """Select row keys for chart envelope from structured analytics payloads."""
    if not isinstance(analytics_data, dict):
        return []
    if intent in {"rank_locations", "metric_breakdown", "derived_metric", "budget_vs_actual"}:
        return list(analytics_data.get("locations") or [])[:50]
    if intent in {"rank_time_periods"}:
        return list(analytics_data.get("periods") or [])[:50]
    if intent == "peak_store_daily_revenue":
        rows = analytics_data.get("top_store_days") or []
        if rows:
            return rows[:50]
        leader = analytics_data.get("leader")
        return [leader] if leader else []
    if intent == "trend_summary":
        return list(analytics_data.get("rows") or [])[:60]
    if intent == "compare_locations":
        return list(analytics_data.get("locations") or [])[:20]
    if intent == "category_breakdown":
        rows = []
        for st in analytics_data.get("stores") or []:
            if not isinstance(st, dict):
                continue
            for cat in st.get("categories") or []:
                rows.append({
                    "location_name": st.get("location_name"),
                    "category": cat.get("category"),
                    "revenue": cat.get("revenue"),
                })
        return rows[:40]
    if intent == "compare_periods":
        pa = analytics_data.get("period_a") or {}
        pb = analytics_data.get("period_b") or {}
        return [
            {"label": pa.get("label", "A"), "value": pa.get("value")},
            {"label": pb.get("label", "B"), "value": pb.get("value")},
        ]
    if intent == "correlation_check":
        return [
            {
                "network_revenue": analytics_data.get("network_daily_revenue_series", []) and 1,
                "note": "scatter built client-side from series when present",
            }
        ]
    if intent == "revenue_door_series":
        return list(analytics_data.get("series") or [])[:90]
    return []


def build_chart_envelope(intent: str, plan: dict, analytics_data: Optional[dict]) -> Optional[dict]:
    """Optional chart object for the API response."""
    if not plan.get("requires_chart") and intent not in {
        "rank_locations",
        "rank_time_periods",
        "compare_locations",
        "compare_periods",
        "trend_summary",
    }:
        return None
    from ai.followups import chart_config_for_intent

    cfg = chart_config_for_intent(intent, plan.get("metric") or "revenue")
    if not cfg or not analytics_data:
        return None
    rows = chart_rows_for_payload(intent, analytics_data)
    if not rows:
        return None
    if intent == "category_breakdown":
        valid = [
            r for r in rows
            if float(r.get("revenue") or r.get("metric_value") or 0) > 0
            and str(r.get("category") or r.get("label") or "").strip()
        ]
        if len(valid) < 2:
            return None
        rows = valid
    metric = str(plan.get("metric") or "metric").replace("_", " ").title()
    if intent == "category_breakdown":
        metric = "Core sales"
    tf = (analytics_data.get("timeframe") or plan.get("timeframe") or {}) if isinstance(analytics_data, dict) else {}
    label = str(tf.get("label") or "")
    title_parts = [metric, intent.replace("_", " ").title()]
    if label:
        title_parts.append(label)
    return {
        **cfg,
        "title": " — ".join(title_parts),
        "rows": rows,
    }


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
