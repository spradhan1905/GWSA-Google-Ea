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
    wants_rank_time_periods,
    wants_store_best_day,
)
from ai.planner_prompt import PLANNER_SYSTEM_PROMPT
from ai.planner_validation import parse_json_content, validate_and_resolve_llm_json
from ai.composer import azure_openai_configured, get_azure_openai_client

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


def _carry_forward_timeframe(plan: dict, session: SessionState) -> dict:
    """Reuse last turn's calendar window when the user gives a follow-up without repeating the month."""
    if plan.get("timeframe"):
        return plan
    lt = session.last_timeframe
    if not isinstance(lt, dict) or not lt.get("start"):
        return plan
    intent = plan.get("intent")
    if intent not in ("rank_time_periods", "peak_store_daily_revenue", "correlation_check"):
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
                    model=Config.AZURE_OPENAI_DEPLOYMENT,
                    messages=[
                        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Session: {sess.to_context_string()}\n\nUser: {text_in}"
                            ),
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=500,
                    timeout=min(timeout, 15.0),
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
                plan = _carry_forward_timeframe(plan, sess)
                return _apply_rank_time_period_override(plan, text_in, sess)
            except Exception as ex:
                _LOG.warning("LLM planner failed; using heuristics: %s", ex)

    # Heuristic fallback (V1)
    h_plan = plan_request_heuristic(text_in, store_context or "", history)
    h_plan["planner_source"] = "heuristic"
    h_plan["plan_confidence"] = "medium"
    h_plan["requires_chart"] = False
    h_plan["resolved_from_followup"] = rq.from_pending_followup
    h_plan = _carry_forward_timeframe(h_plan, sess)
    return _apply_rank_time_period_override(h_plan, text_in, sess)
