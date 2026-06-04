"""LLM-assisted planner with structured JSON output and V1 heuristic fallback."""
from __future__ import annotations

import logging
import re
from typing import Optional


from config import Config

from ai.memory import SessionState, resolve_references
from ai.planner_heuristic import (
    detect_metric,
    match_store_names,
    parse_timeframe,
    plan_request_heuristic,
    wants_chart,
    wants_rank_time_periods,
    wants_store_best_day,
    wants_store_comparison,
)
from ai.planner_prompt import PLANNER_SYSTEM_PROMPT
from ai.planner_validation import parse_json_content, validate_and_resolve_llm_json
from ai.composer import azure_openai_configured, get_azure_openai_client
from ai.openai_compat import merge_chat_completion_kwargs

_LOG = logging.getLogger(__name__)


def _is_greeting_message(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t or len(t) > 60:
        return False
    return bool(
        re.match(r"^(hi|hello|hey|good morning|good afternoon)\b[!.\s]*$", t)
    )


def _env_use_llm_planner() -> bool:
    import os
    v = (os.environ.get("USE_LLM_PLANNER") or "true").strip().lower()
    return v not in {"false", "0", "no", "off"}


def _apply_rank_time_period_override(
    plan: dict,
    user_message: str,
    session: SessionState,
) -> dict:
    """
    When the user clearly asks which calendar day/date had the peak metric, force
    rank_time_periods (daily TotalCore) instead of rank_locations (monthly totals per store).

    The LLM often mislabels these as rank_locations because of words like 'highest' and a
    store name.
    """
    text_in = (user_message or "").strip()
    if not (wants_rank_time_periods(text_in) or wants_store_best_day(text_in)):
        return plan

    from db.queries import get_location_catalog

    catalog = get_location_catalog(limit=80)
    tf = plan.get("timeframe")
    if not isinstance(tf, dict) or not tf.get("start"):
        tf = parse_timeframe(text_in)
    if (not isinstance(tf, dict) or not tf.get("start")) and session.last_timeframe:
        lt = session.last_timeframe
        if isinstance(lt, dict) and lt.get("start"):
            tf = lt

    names = [str(n).strip() for n in (plan.get("store_names") or []) if str(n).strip()]
    if not names:
        names = match_store_names(text_in, catalog)

    out = dict(plan)
    out["intent"] = "rank_time_periods"
    out["action"] = "rank_time_periods"
    out["grain"] = "day"
    if isinstance(tf, dict) and tf.get("start"):
        out["timeframe"] = tf
    if names:
        out["store_names"] = names[:2]
    m = detect_metric(text_in)
    if m:
        out["metric"] = m
    return out


def _finalize_plan(
    plan: dict,
    user_message: str,
    session: SessionState,
    store_context: Optional[str],
) -> dict:
    """
    Chart flags, YTD/compare timeframe fill-in, and rescue LLM/heuristic 'unsupported' when
    the message clearly names two stores and a metric (e.g. donation comparison graph).
    """
    from db.queries import get_location_catalog

    text_in = (user_message or "").strip()
    out = dict(plan)
    catalog = get_location_catalog(limit=80)

    if wants_chart(text_in):
        out["requires_chart"] = True

    matched = match_store_names(text_in, catalog)
    if len(matched) >= 2:
        names = matched[:2]
    else:
        names = [str(n).strip() for n in (out.get("store_names") or []) if str(n).strip()]
    if len(names) < 2:
        if len(matched) >= 1:
            names = matched[:2]
        elif len(names) == 1 and session.last_store_names:
            prior = [str(n).strip() for n in session.last_store_names if str(n).strip()]
            combined = names + [p for p in prior if p not in names]
            if len(combined) >= 2:
                names = combined[:2]
        elif len(names) < 2 and session.last_store_names:
            names = [str(n).strip() for n in session.last_store_names[:2] if str(n).strip()]

    tf = out.get("timeframe")
    if not isinstance(tf, dict) or not tf.get("start"):
        tf = parse_timeframe(text_in)
    if (not isinstance(tf, dict) or not tf.get("start")) and session.last_timeframe:
        lt = session.last_timeframe
        if isinstance(lt, dict) and lt.get("start"):
            tf = lt
    if isinstance(tf, dict) and tf.get("start"):
        out["timeframe"] = tf

    if out.get("intent") == "unsupported" and len(names) >= 2 and isinstance(tf, dict) and tf.get("start"):
        if wants_store_comparison(text_in, len(names)) or wants_chart(text_in):
            out["intent"] = "compare_locations"
            out["action"] = "compare_locations"
            out["store_names"] = names[:2]
            out["metric"] = detect_metric(text_in)
            out["requires_chart"] = wants_chart(text_in) or bool(out.get("requires_chart"))

    if out.get("intent") == "compare_locations":
        if len(names) >= 2:
            out["store_names"] = names[:2]
        if not out.get("metric"):
            out["metric"] = detect_metric(text_in)
        if not isinstance(out.get("timeframe"), dict) or not out["timeframe"].get("start"):
            if isinstance(tf, dict) and tf.get("start"):
                out["timeframe"] = tf

    if out.get("intent") == "category_breakdown" and len(names) >= 1:
        out["store_names"] = names[:3]

    return out


def _carry_forward_stores(plan: dict, session: SessionState, user_message: str) -> dict:
    """Reuse store names from the prior turn for short follow-ups."""
    from db.queries import get_location_catalog

    names = [str(n).strip() for n in (plan.get("store_names") or []) if str(n).strip()]
    catalog = get_location_catalog(limit=80)
    explicit = match_store_names(user_message or "", catalog)
    if len(explicit) >= 2:
        out = dict(plan)
        out["store_names"] = explicit[:2]
        return out
    if names:
        return plan
    prior = [str(n).strip() for n in (session.last_store_names or []) if str(n).strip()]
    if not prior:
        return plan
    low = (user_message or "").lower()
    triggers = (
        "categor", "both", "them", "those", "add door", "chart", "graph", "go deeper",
        "more detail", "donations", "donation count", "expense ratio", "revenue per", "per visitor",
        "same month", "same period", "monthly trend", "explain", "break down", "compare them",
        "what about", "now show", "now add", "put that", "overview", "instead of",
        "this year", "ytd", "draw a", "draw the", "comparison",
    )
    if not any(t in low for t in triggers):
        return plan
    out = dict(plan)
    out["store_names"] = prior[:3]
    if out.get("intent") in (None, "unsupported", "clarification_needed"):
        if "categor" in low:
            out["intent"] = "category_breakdown"
            out["action"] = "category_breakdown"
        elif any(x in low for x in ("chart", "graph", "visual", "plot", "draw")):
            out["intent"] = "compare_locations"
            out["action"] = "compare_locations"
        elif any(x in low for x in ("door", "donation", "expense", "visitor", "trend")):
            out["intent"] = "compare_locations"
            out["action"] = "compare_locations"
    return out


def _carry_forward_timeframe(plan: dict, session: SessionState) -> dict:
    """Reuse last turn's calendar window when the user gives a follow-up without repeating the month."""
    if plan.get("timeframe"):
        return plan
    lt = session.last_timeframe
    if not isinstance(lt, dict) or not lt.get("start"):
        return plan
    intent = plan.get("intent")
    if intent not in (
        "rank_time_periods",
        "peak_store_daily_revenue",
        "correlation_check",
        "compare_locations",
        "category_breakdown",
        "multi_metric_summary",
    ):
        return plan
    p = dict(plan)
    p["timeframe"] = lt
    action_map = {
        "rank_time_periods": "rank_time_periods",
        "peak_store_daily_revenue": "peak_store_daily_revenue",
        "correlation_check": "correlation_check",
    }
    if intent in action_map:
        p["action"] = action_map[intent]
    return p


def plan_request(
    user_message: str,
    store_context: Optional[str],
    history: Optional[list] = None,
    session: Optional[SessionState] = None,
) -> dict:
    """
    Produce an execution plan for analytics_actions.
    Tries Azure OpenAI JSON planner first (fast timeout), then falls back to regex heuristics.
    """
    history = history or []
    sess = session or SessionState()
    rq = resolve_references(user_message, sess, store_context)
    text_in = rq.text

    if _is_greeting_message(text_in):
        return {
            "intent": "greeting",
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
            "planner_source": "router",
            "plan_confidence": "high",
            "resolved_from_followup": rq.from_pending_followup,
        }

    if _env_use_llm_planner() and azure_openai_configured():
        client = get_azure_openai_client()
        if client:
            try:
                timeout = float(getattr(Config, "AI_PLANNER_TIMEOUT_SEC", 3.0) or 3.0)
                response = client.chat.completions.create(
                    **merge_chat_completion_kwargs(
                        {
                            "model": Config.AZURE_OPENAI_DEPLOYMENT,
                            "messages": [
                                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                                {
                                    "role": "user",
                                    "content": (
                                        f"Session: {sess.to_context_string()}\n\nUser: {text_in}"
                                    ),
                                },
                            ],
                            "response_format": {"type": "json_object"},
                            "temperature": 0.0,
                            "timeout": min(timeout, 15.0),
                        },
                        max_tokens=500,
                    )
                )
                raw_content = (response.choices[0].message.content or "").strip()
                parsed = parse_json_content(raw_content)
                from db.queries import get_location_catalog

                catalog = get_location_catalog(limit=80)
                plan, clar = validate_and_resolve_llm_json(
                    parsed, sess, store_context, catalog, text_in
                )
                plan["planner_source"] = "llm"
                if clar:
                    plan["clarification_message"] = clar
                plan["resolved_from_followup"] = rq.from_pending_followup
                plan = _carry_forward_stores(plan, sess, text_in)
                plan = _carry_forward_timeframe(plan, sess)
                plan = _finalize_plan(plan, text_in, sess, store_context)
                return _apply_rank_time_period_override(plan, text_in, sess)
            except Exception as ex:
                _LOG.warning("LLM planner failed; using heuristics: %s", ex)

    # Heuristic fallback (V1)
    h_plan = plan_request_heuristic(text_in, store_context or "", history)
    h_plan["planner_source"] = "heuristic"
    h_plan["plan_confidence"] = "medium"
    h_plan["resolved_from_followup"] = rq.from_pending_followup
    h_plan = _carry_forward_stores(h_plan, sess, text_in)
    h_plan = _carry_forward_timeframe(h_plan, sess)
    h_plan = _finalize_plan(h_plan, text_in, sess, store_context)
    return _apply_rank_time_period_override(h_plan, text_in, sess)
