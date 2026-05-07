"""
GWSA GeoAnalytics — AI Chat Route
POST /api/chat — proxies to Azure OpenAI (key never in browser). V2 pipeline.
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import limiter, ChatRequestSchema
from config import Config

from db.analytics_actions import (
    coerce_plan_for_daily_peak_questions,
    coerce_rank_time_period_session_store,
)

from ai.composer import (
    azure_openai_configured,
    build_composer_messages,
    get_azure_openai_client,
)
from ai.context import build_chart_envelope, data_gap_code
from ai.followups import build_followups
from ai.memory import SessionState, merge_session_after_turn, set_pending_followups
from ai.planner import plan_request
from ai.responses import (
    chat_success_payload,
    correlation_timeframe_required_gap_body,
    demo_reply,
    describe_data_gap,
    provider_error_response,
    quota_fallback_reply,
    store_anchor_required_gap_body,
    timeframe_required_gap_body,
    unsupported_question_body,
)
from ai.router import run_retrieval

chat_bp = Blueprint("chat", __name__)

_GREETING_REPLY = (
    "Hi—I'm the GWSA GeoAnalytics assistant. Ask me about store revenue, door traffic, rankings, "
    "month-over-month comparisons, or how a specific location is performing. "
    "For example: which store had the highest revenue in March, or how Bandera is doing this month."
)


def _plan_used_summary(plan: dict) -> dict:
    m = plan.get("_llm_metrics") if plan.get("_llm_metrics") else None
    if not m and plan.get("metric"):
        m = [plan.get("metric")]
    return {
        "intent": plan.get("intent"),
        "metrics": m or [],
        "grain": plan.get("grain"),
        "scope": plan.get("scope"),
    }


def _response_type_for(plan: dict, data_action: str, analytics_data: dict) -> str:
    if data_gap_code(plan, data_action or "", analytics_data or {}):
        return "partial_answer"
    return "answer"


@chat_bp.route('/api/chat', methods=['POST'])
@limiter.limit("45 per minute")
def chat():
    if not Config.ENABLE_AI:
        return jsonify(error='AI assistant is disabled for this environment'), 403

    schema = ChatRequestSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    user_message = data['message']
    store_context = data.get('store_context')
    history = data.get('conversation_history', [])
    session = SessionState.from_payload(data.get('session_state'))

    azure_client = get_azure_openai_client() if azure_openai_configured() else None
    if not azure_client:
        return jsonify({
            'reply': demo_reply(user_message, store_context),
            'sql_used': None,
            'data': None,
            'response_type': 'demo',
        })

    plan = plan_request(user_message, store_context, history, session=session)

    if plan.get("clarification_message"):
        return jsonify({
            "reply": plan["clarification_message"],
            "response_type": "clarification_needed",
            "sql_used": None,
            "data": None,
            "session_state": session.to_payload(),
            "plan_used": _plan_used_summary(plan),
        })

    plan = coerce_plan_for_daily_peak_questions(dict(plan), user_message)
    plan = coerce_rank_time_period_session_store(plan, user_message, session.last_store_names)

    if plan.get("intent") == "greeting":
        merge_session_after_turn(session, {**plan, "intent": "greeting"}, None, store_context)
        set_pending_followups(session, [
            "How are stores doing this month?",
            "Which store had the highest revenue in March?",
            "What data can I ask about?",
        ])
        return jsonify({
            "reply": _GREETING_REPLY,
            "response_type": "answer",
            "sql_used": None,
            "data": None,
            "session_state": session.to_payload(),
            "followups": session.pending_followups,
            "plan_used": {"intent": "greeting"},
        })

    if plan.get("intent") == "unsupported":
        body = unsupported_question_body()
        body["session_state"] = session.to_payload()
        body["response_type"] = "data_gap"
        return jsonify(body)

    if plan.get("intent") in ("rank_time_periods", "peak_store_daily_revenue") and not plan.get("timeframe"):
        body = timeframe_required_gap_body()
        body["session_state"] = session.to_payload()
        return jsonify(body)

    if plan.get("intent") == "correlation_check" and not plan.get("timeframe"):
        body = correlation_timeframe_required_gap_body()
        body["session_state"] = session.to_payload()
        return jsonify(body)

    if plan.get("intent") in {"trend_summary", "multi_metric_summary", "map_context_summary"}:
        if not plan.get("trend_store_ref"):
            which = {
                "trend_summary": "KPI trend charts",
                "multi_metric_summary": "the multi-metric dashboard summary",
                "map_context_summary": "donor geography context",
            }.get(plan["intent"], "that report")
            body = store_anchor_required_gap_body(which)
            body["session_state"] = session.to_payload()
            return jsonify(body)

    data_action, analytics_data = run_retrieval(plan, store_context)

    if plan.get("action") == "revenue_door_series" and not data_action:
        body = store_anchor_required_gap_body("aligned revenue and door-count series")
        body["session_state"] = session.to_payload()
        return jsonify(body)

    gap_desc = describe_data_gap(
        data_gap_code(plan, data_action or '', analytics_data or {}) or "",
    )

    merge_session_after_turn(session, plan, data_action, store_context)
    followups = build_followups(plan.get("intent") or "", plan, analytics_data)
    set_pending_followups(session, followups)

    chart = build_chart_envelope(plan.get("intent") or "", plan, analytics_data)
    response_type = _response_type_for(plan, data_action or "", analytics_data or {})
    plan_used = _plan_used_summary(plan)
    composer_timeout = float(getattr(Config, "AI_COMPOSER_TIMEOUT_SEC", 8.0) or 8.0)

    try:
        messages = build_composer_messages(
            user_message,
            session,
            plan,
            data_action,
            analytics_data,
            gap_desc,
            history,
        )
        try:
            response = azure_client.chat.completions.create(
                model=Config.AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                timeout=min(composer_timeout, 60.0),
            )
            reply = (response.choices[0].message.content or "").strip()
            if not reply:
                reply = quota_fallback_reply(data_action or "", analytics_data or {})
        except Exception as e1:
            msg = str(e1).lower()
            if any(x in msg for x in ("timeout", "timed out", "deadline")):
                try:
                    short_msgs = [messages[0], messages[-1]]
                    response = azure_client.chat.completions.create(
                        model=Config.AZURE_OPENAI_DEPLOYMENT,
                        messages=short_msgs,
                        timeout=5.0,
                    )
                    reply = (response.choices[0].message.content or "").strip()
                    if not reply:
                        reply = quota_fallback_reply(data_action or "", analytics_data or {})
                except Exception:
                    reply = quota_fallback_reply(data_action or "", analytics_data or {})
            elif any(x in msg for x in ("429", "quota", "rate limit", "too many requests")):
                reply = quota_fallback_reply(data_action or "", analytics_data or {})
            else:
                return provider_error_response(e1, data_action, analytics_data)
        return jsonify(
            chat_success_payload(
                reply,
                plan,
                data_action,
                analytics_data,
                session_payload=session.to_payload(),
                followups=followups,
                chart=chart,
                response_type=response_type,
                plan_used=plan_used,
            )
        )
    except Exception as e:
        return provider_error_response(e, data_action, analytics_data)
