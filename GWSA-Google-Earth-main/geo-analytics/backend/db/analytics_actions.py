"""Approved, parameterized analytics retrievals safe for chat (no dynamic SQL)."""
from datetime import date
from typing import Any, Optional, Sequence, Tuple

from ai.planner_heuristic import (
    detect_metric,
    match_store_names,
    parse_timeframe,
    wants_rank_time_periods,
    wants_store_best_day,
)

from db.queries import (
    _sum_field,
    budget_vs_actual_summary_for_store,
    build_data_catalog,
    compare_locations,
    compare_revenue_categories,
    compare_period_totals,
    donor_map_summary,
    get_donations,
    get_door_count,
    get_financials,
    get_location_catalog,
    get_location_summary,
    get_revenue_door_count_series,
    resolve_location_reference,
    multi_metric_snapshot,
    network_correlation_revenue_door,
    peak_store_daily_revenue,
    rank_donation_days,
    rank_donation_days_for_store,
    rank_door_count_days,
    rank_door_count_days_for_store,
    rank_locations,
    rank_revenue_days,
    rank_revenue_days_for_store,
    rank_store_revenue,
    rank_stores_budget_variance,
    resolve_location_reference,
    revenue_per_visit_by_store,
    trend_summary_for_chat,
)


def coerce_plan_for_daily_peak_questions(plan: dict, user_message: Optional[str]) -> dict:
    """
    Final safety net: questions that clearly ask for a calendar day / date peak must not run
    rank_locations (monthly-style totals per store).

    Older planner builds or stale deployments may still emit rank_locations; fix at execution time.
    """
    if not isinstance(plan, dict) or not user_message or not str(user_message).strip():
        return plan
    text = str(user_message).strip()
    if not (wants_rank_time_periods(text) or wants_store_best_day(text)):
        return plan
    if plan.get("action") not in ("rank_locations", "rank_time_periods", "none") and plan.get(
        "intent"
    ) != "rank_time_periods":
        # Avoid stomping compares, peaks, summaries, or other specialized actions.
        return plan
    p = dict(plan)
    tf = p.get("timeframe")
    if not isinstance(tf, dict) or not tf.get("start"):
        tf = parse_timeframe(text)
    if not isinstance(tf, dict) or not tf.get("start"):
        return plan
    p["intent"] = "rank_time_periods"
    p["action"] = "rank_time_periods"
    p["grain"] = "day"
    p["timeframe"] = tf
    dm = detect_metric(text)
    if dm:
        p["metric"] = dm
    if not (p.get("store_names") or []):
        p["store_names"] = match_store_names(text, get_location_catalog(limit=80))[:2]
    return p


def _implies_network_wide_time_ranking(user_message: Optional[str]) -> bool:
    """True when the user asked for totals across stores, not a continuation focused on one store."""
    if not user_message or not str(user_message).strip():
        return False
    low = str(user_message).lower()
    needles = (
        "all stores",
        "every store",
        "across stores",
        "each store",
        "all locations",
        "network wide",
        "network-wide",
        "whole network",
        "company wide",
        "company-wide",
        "entire retail",
        "retail chain",
        "sum across",
        "combined for all",
    )
    return any(n in low for n in needles)


def coerce_rank_time_period_session_store(
    plan: dict,
    user_message: Optional[str],
    last_store_names: Optional[Sequence[Any]],
) -> dict:
    """
    If rank_time_periods has no resolved store yet, carry forward exactly one previously discussed
    store so ambiguous follow-ups (e.g. chip text omitting store name) use per-location daily totals
    instead of ranking network-wide summed days—prevents inflated numbers wrongly narrated as one store.
    """
    if not isinstance(plan, dict):
        return plan
    if plan.get("action") != "rank_time_periods" and plan.get("intent") != "rank_time_periods":
        return plan
    names = plan.get("store_names") or []
    if isinstance(names, str):
        names = [names]
    names = [str(n).strip() for n in names if str(n).strip()]
    if len(names) >= 1:
        return plan
    if plan.get("use_viewing_store") or plan.get("trend_store_ref"):
        # Executor can resolve viewing / trend anchors without explicit store_names.
        return plan
    if _implies_network_wide_time_ranking(user_message):
        return plan
    if last_store_names is None:
        last_store_names = []
    ln = (
        last_store_names
        if isinstance(last_store_names, (list, tuple))
        else [last_store_names]
    )
    carried = [str(x).strip() for x in ln if x and str(x).strip()]
    if len(carried) != 1:
        return plan
    p = dict(plan)
    p["store_names"] = [carried[0]]
    # Hint for planner payloads / callers; executor keys off single store_names name.
    p["scope"] = "location"
    return p


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
                elif metric == "donations":
                    rows = get_donations(location_id, timeframe["start"], timeframe["end"])
                    metrics = {"donations": round(_sum_field(rows, "Donations"), 2)}
                else:
                    # Daily core revenue from TotalCoreTableFinal (not monthly financial rollup).
                    rows = get_financials(
                        location_id, timeframe["start"], timeframe["end"], this_month=True
                    )
                    metrics = {"revenue": _sum_field(rows, "NetRevenue")}
                data = {
                    "location_id": location_id,
                    "location_name": location.get("LocationName"),
                    "location_type": location.get("LocationType"),
                    "metric": metric,
                    "grain": "day",
                    "timeframe": timeframe,
                    "metrics": metrics,
                    "rows": rows,
                }
                if metric == "revenue":
                    data["revenue_grain"] = "daily_core"
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

    elif action == "category_breakdown":
        if timeframe:
            refs = []
            for nm in list(plan.get("store_names") or []):
                loc = resolve_location_reference(str(nm))
                if loc:
                    refs.append(str(loc["LocationID"]))
            if plan.get("use_viewing_store") and viewing_location:
                vid = str(viewing_location["LocationID"])
                if vid not in refs:
                    refs.append(vid)
            if refs:
                data = compare_revenue_categories(
                    refs,
                    timeframe["start"],
                    timeframe["end"],
                )
                if data.get("stores"):
                    data["timeframe"] = timeframe
                    selected_action = "category_breakdown"

    elif action == "peak_store_daily_revenue":
        if timeframe:
            scope_arg = plan.get("scope") or "all_retail_stores"
            data = peak_store_daily_revenue(
                timeframe["start"],
                timeframe["end"],
                scope=scope_arg,
                timeframe_label=timeframe.get("label"),
                top_pairs=max(int(plan.get("limit") or 5), 5),
            )
            if data is not None:
                selected_action = "peak_store_daily_revenue"

    elif action == "rank_time_periods":
        if timeframe:
            scope_arg = plan.get("scope") or "all_retail_stores"
            label = timeframe.get("label")
            names = plan.get("store_names") or []
            single_id: Optional[str] = None
            if len(names) == 1:
                loc_one = resolve_location_reference(names[0])
                if loc_one:
                    single_id = str(loc_one["LocationID"])
            elif plan.get("use_viewing_store") and viewing_location:
                single_id = str(viewing_location["LocationID"])
            elif plan.get("trend_store_ref"):
                loc_tr = resolve_location_reference(plan["trend_store_ref"])
                if loc_tr:
                    single_id = str(loc_tr["LocationID"])

            use_network = len(names) > 1 or not single_id

            if metric == "door_count":
                if not use_network and single_id:
                    data = rank_door_count_days_for_store(
                        single_id,
                        timeframe["start"],
                        timeframe["end"],
                        limit=plan["limit"],
                        timeframe_label=label,
                    )
                else:
                    data = rank_door_count_days(
                        timeframe["start"],
                        timeframe["end"],
                        scope=scope_arg,
                        limit=plan["limit"],
                        timeframe_label=label,
                    )
            elif metric == "donations":
                if not use_network and single_id:
                    data = rank_donation_days_for_store(
                        single_id,
                        timeframe["start"],
                        timeframe["end"],
                        limit=plan["limit"],
                        timeframe_label=label,
                    )
                else:
                    data = rank_donation_days(
                        timeframe["start"],
                        timeframe["end"],
                        scope=scope_arg,
                        limit=plan["limit"],
                        timeframe_label=label,
                    )
            else:
                if not use_network and single_id:
                    data = rank_revenue_days_for_store(
                        single_id,
                        timeframe["start"],
                        timeframe["end"],
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
                tag = ":store" if (not use_network and single_id) else ""
                selected_action = f"rank_periods:{metric}:day{tag}"

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
                    "revenue", "door_count", "donations", "net_income", "operating_expenses",
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

    elif action == "budget_vs_actual":
        if timeframe:
            scope_arg = plan.get("scope") or "all_retail_stores"
            label = timeframe.get("label")
            ref = _target_store_ref()
            if not ref and store_context:
                loc_ctx = resolve_location_reference(store_context)
                if loc_ctx:
                    ref = str(loc_ctx["LocationID"])
            text_low = (plan.get("_user_text") or "").lower()
            network_rank = any(
                x in text_low
                for x in ("which store", "top ", "rank", "beat", "beating", "stores", "furthest")
            )
            single_store = bool(ref) and not network_rank
            if single_store and ref:
                loc = resolve_location_reference(ref)
                if loc:
                    sid = str(loc["LocationID"])
                    data = budget_vs_actual_summary_for_store(
                        sid,
                        timeframe["start"],
                        timeframe["end"],
                        timeframe_label=label,
                    )
                    selected_action = f"budget_vs_actual:store:{sid}"
            else:
                sort = "attainment_desc"
                low = (plan.get("_user_text") or "").lower()
                if "below budget" in low or "under budget" in low or "furthest below" in low:
                    sort = "attainment_asc"
                elif "over budget" in low or "above budget" in low:
                    sort = "variance_desc"
                data = rank_stores_budget_variance(
                    timeframe["start"],
                    timeframe["end"],
                    scope=scope_arg,
                    limit=plan["limit"],
                    timeframe_label=label,
                    sort=sort,
                )
                selected_action = "budget_vs_actual:rank"

    return selected_action, data
