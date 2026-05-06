"""Approved, parameterized analytics retrievals safe for chat (no dynamic SQL)."""
from typing import Optional, Tuple, Any

from datetime import date

from db.queries import (
    build_data_catalog,
    compare_locations,
    compare_period_totals,
    donor_map_summary,
    get_door_count,
    get_location_summary,
    get_revenue_door_count_series,
    multi_metric_snapshot,
    network_correlation_revenue_door,
    rank_door_count_days,
    rank_locations,
    rank_revenue_days,
    rank_store_revenue,
    resolve_location_reference,
    revenue_per_visit_by_store,
    trend_summary_for_chat,
    _sum_field,
)


def execute_approved_action(plan: dict, store_context: str) -> Tuple[Optional[str], Any]:
    """Run only approved helpers; returns (sql_used / action label, structured data)."""
    action = plan["action"]
    metric = plan["metric"]
    timeframe = plan.get("timeframe")
    selected_action = None
    data = None

    viewing_location = resolve_location_reference(store_context) if store_context else None

    def _target_store_ref() -> Optional[str]:
        if plan.get("store_names"):
            return plan["store_names"][0]
        if plan.get("use_viewing_store") and viewing_location:
            return str(viewing_location["LocationID"])
        if plan.get("trend_store_ref"):
            return plan["trend_store_ref"]
        return None

    if action == "location_summary":
        target_ref = _target_store_ref()
        if target_ref and timeframe:
            location = resolve_location_reference(target_ref)
            if location:
                location_id = str(location["LocationID"])
                if metric == "door_count":
                    rows = get_door_count(location_id, timeframe["start"], timeframe["end"])
                    metrics = {"door_count": int(round(_sum_field(rows, "DonorVisits")))}
                else:
                    rows = get_financials(location_id, timeframe["start"], timeframe["end"])
                    metrics = {"revenue": _sum_field(rows, "NetRevenue")}
                data = {
                    "location_id": location_id,
                    "location_name": location.get("LocationName"),
                    "location_type": location.get("LocationType"),
                    "metric": metric,
                    "timeframe": timeframe,
                    "metrics": metrics,
                    "rows": rows,
                }
                selected_action = f"location_summary:{metric}"
        elif target_ref:
            data = get_location_summary(target_ref)
            if data:
                selected_action = "location_summary"

    elif action == "compare_locations":
        refs = list(plan["store_names"])
        if plan["use_viewing_store"] and viewing_location:
            refs.append(str(viewing_location["LocationID"]))
        data = compare_locations(metric, refs, timeframe=timeframe)
        if data.get("locations") and len(data["locations"]) >= 2:
            selected_action = f"compare_locations:{metric}"

    elif action == "rank_time_periods":
        if timeframe:
            scope_arg = plan.get("scope") or "all_retail_stores"
            label = timeframe.get("label")
            if metric == "door_count":
                data = rank_door_count_days(
                    timeframe["start"],
                    timeframe["end"],
                    scope=scope_arg,
                    limit=plan["limit"],
                    timeframe_label=label,
                )
            else:
                data = rank_revenue_days(
                    timeframe["start"],
                    timeframe["end"],
                    scope=scope_arg,
                    limit=plan["limit"],
                    timeframe_label=label,
                )
            if data is not None:
                selected_action = f"rank_periods:{metric}:day"

    elif action == "rank_locations":
        data = rank_locations(metric, plan["limit"], timeframe=timeframe)
        if data.get("locations"):
            selected_action = f"rank_locations:{metric}"

    elif action == "data_catalog":
        data = build_data_catalog()
        selected_action = "data_catalog"

    elif action == "trend_summary":
        ref = plan.get("trend_store_ref") or store_context
        months = plan.get("trend_months") or 12
        if ref:
            loc = resolve_location_reference(str(ref))
            if loc:
                sid = str(loc["LocationID"])
                data = trend_summary_for_chat(sid, months=months)
                selected_action = f"trend_summary:{months}m:{sid}"

    elif action == "metric_breakdown":
        if timeframe:
            data = rank_store_revenue(
                timeframe["start"],
                timeframe["end"],
                metric=metric if metric in {
                    "revenue", "door_count", "net_income", "operating_expenses",
                    "personnel_expenses", "expense_ratio",
                } else "revenue",
                scope=plan.get("scope") or "all_retail_stores",
                limit=plan["limit"],
                timeframe_label=timeframe.get("label"),
            )
            if data.get("locations"):
                selected_action = f"metric_breakdown:{data.get('metric', 'revenue')}"

    elif action == "multi_metric_summary":
        ref = _target_store_ref()
        if ref and timeframe:
            loc = resolve_location_reference(ref)
            if loc:
                data = multi_metric_snapshot(
                    str(loc["LocationID"]),
                    timeframe["start"],
                    timeframe["end"],
                )
                if not data.get("error"):
                    selected_action = f"multi_metric:{str(loc['LocationID'])}"

    elif action == "compare_periods":
        comp = plan.get("comparison") or {}
        tfa = comp.get("timeframe_a")
        tfb = comp.get("timeframe_b")
        if tfa and tfb:
            data = compare_period_totals(
                metric,
                tfa,
                tfb,
                scope=plan.get("scope") or "all_retail_stores",
            )
            selected_action = f"compare_periods:{metric}"

    elif action == "correlation_check":
        if timeframe:
            data = network_correlation_revenue_door(
                timeframe["start"],
                timeframe["end"],
                scope=plan.get("scope") or "all_retail_stores",
                timeframe_label=timeframe.get("label"),
            )
            selected_action = "correlation:revenue_door"

    elif action == "revenue_door_series":
        ref = _target_store_ref()
        grain = "day"
        tm = timeframe or {}
        ref_str = ""
        if ref and tm.get("start") and tm.get("end"):
            loc = resolve_location_reference(ref)
            if loc:
                ref_str = str(loc["LocationID"])
                span = max(1, abs(date.fromisoformat(tm["end"]) - date.fromisoformat(tm["start"])).days)
                grain = "month" if span > 62 else "day"
                data = get_revenue_door_count_series(
                    ref_str,
                    tm["start"],
                    tm["end"],
                    grain=grain,
                )
                if not data.get("error"):
                    selected_action = f"revenue_door_series:{grain}:{ref_str}"

    elif action == "revenue_per_visit_rank":
        if timeframe:
            data = revenue_per_visit_by_store(
                timeframe["start"],
                timeframe["end"],
                scope=plan.get("scope") or "all_retail_stores",
                limit=plan["limit"],
            )
            if data.get("locations") is not None:
                selected_action = "derived:revenue_per_visit"

    elif action == "map_context_summary":
        ref = _target_store_ref() or store_context
        if ref:
            loc = resolve_location_reference(str(ref))
            if loc:
                sid = str(loc["LocationID"])
                data = donor_map_summary(sid)
                selected_action = f"map_context:{sid}"

    return selected_action, data
