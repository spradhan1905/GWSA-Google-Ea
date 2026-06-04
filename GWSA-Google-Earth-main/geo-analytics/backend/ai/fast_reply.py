"""
Instant factual replies from structured analytics payloads — skips the LLM composer.

Used for rankings, comparisons, totals, budget variance, and donation summaries so users
get an answer in milliseconds after SQL retrieval instead of waiting on Azure OpenAI.
"""
from __future__ import annotations

from typing import Any, Optional


def _money(v: Any) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v: Any) -> str:
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return str(v)


def _period_label(data: dict, plan: dict) -> str:
    tf = (data or {}).get("timeframe") or plan.get("timeframe") or {}
    return str(tf.get("label") or "the selected period").strip()


def _metric_label(metric: str) -> str:
    return {
        "revenue": "core revenue",
        "door_count": "donor visits",
        "donations": "donations",
        "budget_attainment": "budget attainment",
        "net_income": "net income",
        "operating_expenses": "operating expenses",
        "personnel_expenses": "personnel expenses",
        "expense_ratio": "expense ratio",
        "revenue_per_visit": "revenue per visit",
    }.get(metric or "", (metric or "metric").replace("_", " "))


def try_fast_reply(
    plan: dict,
    data_action: Optional[str],
    data: Optional[dict],
    user_message: str = "",
) -> Optional[str]:
    """Return a complete assistant reply when evidence is unambiguous; else None (use LLM)."""
    if not data_action or not isinstance(data, dict) or not data:
        return None

    intent = plan.get("intent") or ""
    metric = plan.get("metric") or data.get("metric") or "revenue"
    period = _period_label(data, plan)
    da = data_action or ""

    if da.startswith("budget_vs_actual:store"):
        name = data.get("location_name") or "That store"
        actual = data.get("actual_revenue")
        budget = data.get("budget_revenue")
        variance = data.get("revenue_variance")
        att = data.get("attainment_pct")
        if actual is None or budget is None:
            return None
        status = "over budget" if (variance or 0) > 0 else "under budget" if (variance or 0) < 0 else "on budget"
        att_bit = f" ({_pct(att)} of budget)" if att is not None else ""
        var_bit = ""
        if variance is not None and float(variance) != 0:
            var_bit = f" — variance { _money(abs(variance))} {'above' if variance > 0 else 'below' } plan."
        return (
            f"For **{period}**, **{name}** recorded **{_money(actual)}** in actual core revenue "
            f"against a budget of **{_money(budget)}**{att_bit}, so the store is **{status}**{var_bit}"
        )

    if da == "budget_vs_actual:rank" or (
        intent == "budget_vs_actual" and data.get("locations")
    ):
        locs = list(data.get("locations") or [])
        if not locs:
            return f"No budget vs actual rows came back for **{period}**."
        top = locs[0]
        nm = top.get("location_name") or "the leading store"
        att = top.get("attainment_pct")
        actual = top.get("actual_revenue")
        budget = top.get("budget_revenue")
        net_actual = sum(float(x.get("actual_revenue") or 0) for x in locs)
        net_budget = sum(float(x.get("budget_revenue") or 0) for x in locs)
        net_att = round(100.0 * net_actual / net_budget, 1) if net_budget > 1e-9 else None
        lines = [
            f"Across retail stores in **{period}**, the network ran **{_money(net_actual)}** actual core revenue "
            f"vs **{_money(net_budget)}** budget"
            + (f" (**{_pct(net_att)}** of plan)." if net_att is not None else "."),
            f"**{nm}** leads at **{_pct(att)}** of budget ({_money(actual)} actual vs {_money(budget)} budget)."
            if att is not None else f"**{nm}** leads with actual **{_money(actual)}** vs budget **{_money(budget)}**.",
        ]
        if len(locs) > 1:
            low = locs[-1]
            lines.append(
                f"Lowest attainment: **{low.get('location_name')}** at **{_pct(low.get('attainment_pct'))}**."
                if low.get("attainment_pct") is not None else ""
            )
        return " ".join(x for x in lines if x)

    if da.startswith("rank_locations:") or da.startswith("metric_breakdown:"):
        locs = list(data.get("locations") or [])
        if not locs:
            return None
        top = locs[0]
        ml = _metric_label(metric)
        val = top.get("metric_value")
        if metric == "door_count":
            val_fmt = f"{int(round(float(val))):,} visits"
        elif metric == "donations":
            val_fmt = _money(val)
        elif metric == "expense_ratio":
            val_fmt = _pct(float(val) * 100) if float(val) <= 1 else _pct(val)
        else:
            val_fmt = _money(val) if metric in {"revenue", "net_income", "operating_expenses", "personnel_expenses"} else str(val)
        return (
            f"For **{period}**, **{top.get('location_name')}** ranks highest for **{ml}** "
            f"at **{val_fmt}**."
        )

    if da.startswith("rank_periods:"):
        periods = list(data.get("periods") or [])
        if not periods:
            return f"No daily {_metric_label(metric)} rows were returned for **{period}**."
        best = periods[0]
        ml = _metric_label(metric)
        val = best.get("metric_value")
        if metric == "door_count":
            val_fmt = f"{int(round(float(val))):,} visits"
        elif metric == "donations":
            val_fmt = _money(val)
        else:
            val_fmt = _money(val)
        scope = data.get("scope")
        store = data.get("location_name")
        if scope == "location" and store:
            return f"For **{store}** in **{period}**, the strongest day for **{ml}** was **{best.get('date')}** at **{val_fmt}**."
        return f"For **{period}**, the top network day for **{ml}** was **{best.get('date')}** at **{val_fmt}**."

    if da == "category_breakdown" or intent == "category_breakdown":
        stores = list(data.get("stores") or [])
        if not stores:
            return None
        period = _period_label(data, plan)
        blocks = []
        for st in stores[:3]:
            cats = list(st.get("categories") or [])
            if not cats:
                continue
            total = float(st.get("total_revenue") or 0) or sum(
                float(c.get("revenue") or 0) for c in cats
            )
            name = st.get("location_name") or "Store"
            lines = [f"**{name}** — **{_money(total)}** total for **{period}**:"]
            for row in cats[:12]:
                rev = float(row.get("revenue") or 0)
                pct = round(100.0 * rev / total, 1) if total > 1e-9 else 0.0
                lines.append(f"- {row.get('category')}: **{_money(rev)}** ({pct}% of store total)")
            src = st.get("category_source") or data.get("source") or {}
            grain = src.get("grain") or ""
            if grain == "gp_sales_category":
                lines.append("(Categories from GP line-level sales / SalesCategoryFromGP.)")
            blocks.append("\n".join(lines))
        if not blocks:
            return None
        if plan.get("requires_chart"):
            return "\n\n".join(blocks) + "\n\nA comparison chart is included below."
        return "\n\n".join(blocks)

    if da.startswith("compare_locations:"):
        if plan.get("requires_chart"):
            return None
        locs = list(data.get("locations") or [])
        if len(locs) < 2:
            return None
        ml = _metric_label(metric)
        a, b = locs[0], locs[1]
        av, bv = a.get("metric_value"), b.get("metric_value")
        try:
            fa, fb = float(av), float(bv)
        except (TypeError, ValueError):
            return None
        if fa >= fb:
            hi, lo = a, b
        else:
            hi, lo = b, a
        if metric == "door_count":
            return (
                f"For **{period}**, **{hi.get('location_name')}** had **{int(round(float(hi.get('metric_value')))):,}** "
                f"donor visits vs **{int(round(float(lo.get('metric_value')))):,}** at **{lo.get('location_name')}**."
            )
        if metric == "donations":
            return (
                f"For **{period}**, **{hi.get('location_name')}** collected **{_money(hi.get('metric_value'))}** in donations "
                f"compared with **{_money(lo.get('metric_value'))}** at **{lo.get('location_name')}**."
            )
        return (
            f"For **{period}**, **{hi.get('location_name')}** leads on **{ml}** at **{_money(hi.get('metric_value'))}** "
            f"vs **{_money(lo.get('metric_value'))}** for **{lo.get('location_name')}**."
        )

    if da.startswith("location_summary:"):
        mets = data.get("metrics") or {}
        name = data.get("location_name") or "The store"
        if metric == "donations" and "donations" in mets:
            return f"For **{period}**, **{name}** collected **{_money(mets['donations'])}** in donations."
        if metric == "door_count" and "door_count" in mets:
            return f"For **{period}**, **{name}** had **{int(mets['door_count']):,}** donor visits."
        if "revenue" in mets:
            return f"For **{period}**, **{name}** recorded **{_money(mets['revenue'])}** in core revenue."

    if da.startswith("compare_periods:"):
        pa = data.get("period_a") or {}
        pb = data.get("period_b") or {}
        va, vb = pa.get("value"), pb.get("value")
        if va is None or vb is None:
            return None
        ml = _metric_label(metric)
        pct = data.get("pct_change_vs_b")
        pct_bit = f" ({pct:+.1f}% vs prior period)" if pct is not None else ""
        if metric == "donations":
            return (
                f"Network **{ml}** was **{_money(va)}** in {pa.get('timeframe', {}).get('label', 'period A')} "
                f"vs **{_money(vb)}** in {pb.get('timeframe', {}).get('label', 'period B')}{pct_bit}."
            )
        if metric == "door_count":
            return (
                f"Network **{ml}** was **{int(round(float(va))):,}** vs **{int(round(float(vb))):,}**{pct_bit}."
            )
        return (
            f"Network **{ml}** was **{_money(va)}** vs **{_money(vb)}**{pct_bit}."
        )

    if da == "peak_store_daily_revenue" and data.get("leader"):
        lead = data["leader"]
        return (
            f"The strongest single-store sales day in **{period}** was **{lead.get('location_name')}** "
            f"on **{lead.get('date')}** at **{_money(lead.get('metric_value'))}**."
        )

    if da == "data_catalog":
        desc = (data.get("description") or "")[:400]
        examples = data.get("example_questions") or []
        n_bank = data.get("question_bank_size") or 0
        parts = [desc] if desc else []
        if n_bank:
            parts.append(f"I am trained on **{n_bank}** example retail analytics questions.")
        if examples:
            parts.append("You can ask things like: " + "; ".join(examples[:6]) + ".")
        return " ".join(parts) if parts else None

    return None
