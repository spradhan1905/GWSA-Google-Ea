"""
GWSA GeoAnalytics — AI Chat Route
POST /api/chat — proxies to Azure OpenAI (key never in browser)
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import limiter, ChatRequestSchema
from config import Config

from ai.composer import (
    azure_openai_configured,
    build_azure_messages,
    build_gemini_user_text,
    get_azure_openai_client,
    get_gemini_model,
)
from ai.context import data_gap_code
from ai.planner import plan_request
from ai.prompts import SYSTEM_CONTEXT
from ai.responses import (
    chat_success_payload,
    correlation_timeframe_required_gap_body,
    demo_reply,
    describe_data_gap,
    provider_error_response,
    store_anchor_required_gap_body,
    timeframe_required_gap_body,
    unsupported_question_body,
)
from ai.router import run_retrieval

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/api/chat', methods=['POST'])
@limiter.limit("10 per minute")
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

    azure_client = get_azure_openai_client() if azure_openai_configured() else None
    gemini_model = None if azure_client else get_gemini_model()
    if not azure_client and (not gemini_model or not Config.GEMINI_API_KEY):
        return jsonify({
            'reply': demo_reply(user_message, store_context),
            'sql_used': None,
            'data': None
        })

    plan = plan_request(user_message, store_context, history)

    if plan.get("intent") == "unsupported":
        return jsonify(unsupported_question_body())

    if plan.get("intent") == "rank_time_periods" and not plan.get("timeframe"):
        return jsonify(timeframe_required_gap_body())

    if plan.get("intent") == "correlation_check" and not plan.get("timeframe"):
        return jsonify(correlation_timeframe_required_gap_body())

    if plan.get("intent") in {"trend_summary", "multi_metric_summary", "map_context_summary"}:
        if not plan.get("trend_store_ref"):
            which = {
                "trend_summary": "KPI trend charts",
                "multi_metric_summary": "the multi-metric dashboard summary",
                "map_context_summary": "donor geography context",
            }.get(plan["intent"], "that report")
            return jsonify(store_anchor_required_gap_body(which))

    data_action, analytics_data = run_retrieval(plan, store_context)

    if plan.get("action") == "revenue_door_series" and not data_action:
        return jsonify(store_anchor_required_gap_body("aligned revenue and door-count series"))

    gap_desc = describe_data_gap(
        data_gap_code(plan, data_action or '', analytics_data or {}) or "",
    )

    try:
        if azure_client:
            response = azure_client.chat.completions.create(
                model=Config.AZURE_OPENAI_DEPLOYMENT,
                messages=build_azure_messages(
                    user_message,
                    store_context,
                    history,
                    data_action,
                    analytics_data,
                    gap_desc,
                ),
                timeout=Config.AI_COMPLETION_TIMEOUT_SEC,
            )
            reply = response.choices[0].message.content or ""
        else:
            response = gemini_model.generate_content(
                f"{SYSTEM_CONTEXT.strip()}\n\n{build_gemini_user_text(
                    user_message,
                    store_context,
                    history,
                    data_action,
                    analytics_data,
                    gap_desc,
                )}"
            )
            reply = response.text
        return jsonify(chat_success_payload(reply, plan, data_action, analytics_data))
    except Exception as e:
        return provider_error_response(e, data_action, analytics_data)
