"""
GWSA GeoAnalytics — AI Chat Route
POST /api/chat — proxies to Azure OpenAI (key never in browser)
"""
import json
import re
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import limiter, ChatRequestSchema
from config import Config

chat_bp = Blueprint('chat', __name__)

SYSTEM_CONTEXT = """
You are a data analyst assistant for Goodwill Industries of San Antonio (GWSA).
Be concise, professional, and data-driven.
Do not mention or infer specific manager names; refer only to roles.
If structured analytics data is provided, use it faithfully and do not invent missing values.
If no structured data is provided, answer generally and say what data is available.
"""

INTENT_ACTIONS = {"none", "location_summary", "compare_locations", "rank_locations"}
INTENT_METRICS = {"revenue", "door_count"}
RANK_HINTS = ("highest", "best", "top", "most", "lowest", "least")
COMPARE_HINTS = ("compare", "vs", "versus", "against")
SUMMARY_HINTS = ("summary", "how is", "how's", "performance", "doing")


def _azure_openai_configured() -> bool:
    return all([
        Config.AZURE_OPENAI_ENDPOINT,
        Config.AZURE_OPENAI_API_KEY,
        Config.AZURE_OPENAI_DEPLOYMENT,
        Config.AZURE_OPENAI_API_VERSION,
    ])


def _get_azure_openai_client():
    try:
        from openai import AzureOpenAI
        return AzureOpenAI(
            api_key=Config.AZURE_OPENAI_API_KEY,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_version=Config.AZURE_OPENAI_API_VERSION,
        )
    except Exception:
        return None


def _get_gemini_model():
    try:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        return genai.GenerativeModel(Config.GEMINI_MODEL)
    except Exception:
        return None


def try_text_to_sql(model, question: str, store_id: str):
    """Attempt to generate and execute a safe SQL query from natural language."""
    return None, None
    # This Month MTD: Config.SQL_THIS_MONTH_REVENUE_OBJECT (default JS_API.dbo.TotalCoreTableFinal)
    schema_hint = """
    Tables:
      Locations(LocationID, LocationName, LocationType, Manager)
      PeopleCounter.dbo.PCounter(LocationID, Date, In; hourly rows aggregate to daily; multiple LocationIDs per store sum Left+Right)
      TotalCoreTableFinal (JS_API.dbo — This Month MTD Core Sales revenue):
        [Date] (DATE), [Revenue] (SUM for MTD), [Unit] (e.g. 20-10-129-12000 — 3rd hyphen segment = Location ID 129),
        [Category] (filter e.g. N'Core Sales'), [sales unit name], Sub_Category, RevenueType, Source
      Legacy line-level POS (not used for This Month KPI): SalesFactFinal (Soldts, SoldStoreId, SalesCategoryFromGP, etc.).
    """
    sql_prompt = f"""
    Schema: {schema_hint}
    Write a single safe SQL Server SELECT query to answer: "{question}"
    Rules: SELECT only. TOP 100 max. No INSERT/UPDATE/DELETE/DROP/EXEC.
    Return ONLY the SQL — no markdown, no explanation.
    """
    try:
        sql_response = model.generate_content(sql_prompt)
        sql_query = sql_response.text.strip()
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()

        if not is_safe_sql(sql_query):
            return None, None

        from db.connection import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        cols = [d[0] for d in cursor.description]
        result = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()
        return sql_query, result
    except Exception:
        return None, None


def _extract_json_object(text: str) -> dict:
    """Parse the first JSON object from a model response."""
    if not text:
        return {}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _history_to_text(history: list) -> str:
    lines = []
    for item in history[-6:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _match_store_names(user_message: str, catalog: list) -> list:
    """Resolve up to two location names directly from the user message."""
    text = (user_message or "").lower()
    matches = []
    for loc in catalog:
        name = str(loc.get("name", "")).strip()
        if not name:
            continue
        name_lc = name.lower()
        normalized = re.sub(r"\s+retail store|\s+donation station|\s+store|\s+station", "", name_lc).strip()
        if name_lc in text or (normalized and normalized in text):
            if name not in matches:
                matches.append(name)
        if len(matches) >= 2:
            break
    return matches


def _detect_metric(user_message: str) -> str:
    text = (user_message or "").lower()
    if any(word in text for word in ("door count", "door counts", "visits", "visitor", "donor")):
        return "door_count"
    return "revenue"


def _plan_request(user_message: str, store_context: str, history: list) -> dict:
    """Choose an approved analytics action with local heuristics to avoid extra AI calls."""
    from db.queries import get_location_catalog

    catalog = get_location_catalog(limit=60)
    text = (user_message or "").lower()
    metric = _detect_metric(user_message)
    store_names = _match_store_names(user_message, catalog)
    use_viewing_store = bool(store_context) and any(token in text for token in ("this store", "selected store", "viewing", "here"))

    numbers = re.findall(r"\b(\d{1,2})\b", text)
    parsed_limit = int(numbers[0]) if numbers else 5

    if any(hint in text for hint in COMPARE_HINTS) and (len(store_names) >= 2 or (len(store_names) == 1 and use_viewing_store)):
        action = "compare_locations"
    elif any(hint in text for hint in RANK_HINTS):
        action = "rank_locations"
    elif len(store_names) == 1 or use_viewing_store or any(hint in text for hint in SUMMARY_HINTS):
        action = "location_summary"
    else:
        action = "none"

    return {
        "action": action,
        "metric": metric,
        "store_names": [str(name).strip()[:80] for name in store_names[:2] if str(name).strip()],
        "use_viewing_store": use_viewing_store,
        "limit": max(1, min(parsed_limit, 10)),
    }


def _quota_fallback_reply(user_message: str, data_action: str, analytics_data: dict) -> str:
    """Return a plain fallback answer when AI is unavailable but approved analytics data exists."""
    if not data_action or not analytics_data:
        return (
            "The AI service is temporarily unavailable or has hit its quota limit. "
            "The data request completed, but I could not generate a full AI narrative right now."
        )

    if data_action.startswith("rank_locations:"):
        locations = analytics_data.get("locations") or []
        metric = analytics_data.get("metric", "revenue")
        if locations:
            leader = locations[0]
            value = leader.get("metric_value")
            return (
                f"The AI service is temporarily unavailable, but based on the approved analytics query, "
                f"{leader.get('location_name')} is currently ranked highest for {metric} "
                f"with a value of {value}."
            )

    if data_action.startswith("compare_locations:"):
        leader = analytics_data.get("leader")
        metric = analytics_data.get("metric", "revenue")
        if leader:
            return (
                f"The AI service is temporarily unavailable, but the comparison completed. "
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

    return (
        "The AI service is temporarily unavailable or has hit its quota limit. "
        "The approved analytics request completed successfully."
    )


def _ai_error_response(exc: Exception, data_action: str, analytics_data: dict):
    """Map AI provider exceptions to useful HTTP responses for the frontend."""
    message = str(exc).strip() or "Unknown AI service error."
    lowered = message.lower()

    if any(token in lowered for token in ("429", "quota", "rate limit", "resource exhausted", "too many requests")):
        return jsonify(
            error="Azure OpenAI quota or rate limit reached. Please wait or increase your Azure OpenAI quota.",
            reply=_quota_fallback_reply("", data_action, analytics_data),
            sql_used=data_action,
            data=analytics_data,
        ), 429

    if any(token in lowered for token in ("api key", "permission denied", "permission", "forbidden", "403", "401", "unauthorized")):
        return jsonify(error=f"Azure OpenAI authentication or access error: {message}"), 502

    if any(token in lowered for token in ("timeout", "timed out", "deadline exceeded", "connection", "unavailable", "503")):
        return jsonify(error=f"Azure OpenAI network or availability error: {message}"), 504

    return jsonify(error=f"AI service error: {message}"), 500


def _execute_approved_action(plan: dict, store_context: str):
    """Run only approved parameterized analytics helpers."""
    from db.queries import compare_locations, get_location_summary, rank_locations, resolve_location_reference

    action = plan["action"]
    metric = plan["metric"]
    selected_action = None
    data = None

    viewing_location = resolve_location_reference(store_context) if store_context else None

    if action == "location_summary":
        target_ref = None
        if plan["store_names"]:
            target_ref = plan["store_names"][0]
        elif plan["use_viewing_store"] and viewing_location:
            target_ref = str(viewing_location["LocationID"])

        if target_ref:
            data = get_location_summary(target_ref)
            if data:
                selected_action = "location_summary"

    elif action == "compare_locations":
        refs = list(plan["store_names"])
        if plan["use_viewing_store"] and viewing_location:
            refs.append(str(viewing_location["LocationID"]))
        data = compare_locations(metric, refs)
        if data.get("locations") and len(data["locations"]) >= 2:
            selected_action = f"compare_locations:{metric}"

    elif action == "rank_locations":
        data = rank_locations(metric, plan["limit"])
        if data.get("locations"):
            selected_action = f"rank_locations:{metric}"

    return selected_action, data


def _build_response_prompt(user_message: str, store_context: str, data_action: str, data: dict) -> str:
    prompt = ""
    if store_context:
        prompt += f"Current viewed location: {store_context}.\n"
    if data_action and data:
        prompt += f"Approved analytics action used: {data_action}.\n"
        prompt += f"Structured analytics data:\n{json.dumps(data, indent=2)}\n\n"
    prompt += f"User question: {user_message}"
    return prompt


def _build_azure_messages(user_message: str, store_context: str, history: list, data_action: str, data: dict) -> list:
    messages = [{"role": "system", "content": SYSTEM_CONTEXT.strip()}]
    for item in history[-6:]:
        role = item.get("role", "user")
        if role not in {"user", "assistant"}:
            role = "user"
        content = str(item.get("content", "")).strip()
        if content:
            messages.append({"role": role, "content": content})
    messages.append({
        "role": "user",
        "content": _build_response_prompt(user_message, store_context, data_action, data),
    })
    return messages


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

    azure_client = _get_azure_openai_client() if _azure_openai_configured() else None
    gemini_model = None if azure_client else _get_gemini_model()
    if not azure_client and (not gemini_model or not Config.GEMINI_API_KEY):
        return jsonify({
            'reply': _demo_reply(user_message, store_context),
            'sql_used': None,
            'data': None
        })

    plan = _plan_request(user_message, store_context, history)
    data_action, analytics_data = _execute_approved_action(plan, store_context)
    full_prompt = _build_response_prompt(user_message, store_context, data_action, analytics_data)

    try:
        if azure_client:
            response = azure_client.chat.completions.create(
                model=Config.AZURE_OPENAI_DEPLOYMENT,
                messages=_build_azure_messages(user_message, store_context, history, data_action, analytics_data),
            )
            reply = response.choices[0].message.content or ""
        else:
            response = gemini_model.generate_content(f"{SYSTEM_CONTEXT}\n\n{full_prompt}")
            reply = response.text
        return jsonify({
            'reply': reply,
            'sql_used': data_action,
            'data': analytics_data
        })
    except Exception as e:
        return _ai_error_response(e, data_action, analytics_data)


def _demo_reply(message: str, store_context: str = None) -> str:
    """Provide helpful demo responses when no AI provider is configured."""
    msg = message.lower()
    store = store_context or "the selected location"

    if 'revenue' in msg or 'income' in msg:
        return f"Based on demo data for {store}, this location shows average monthly net revenue of approximately $145,000 with a healthy expense ratio around 68%. To see live data, configure Azure OpenAI and SQL Server connection."
    elif 'door count' in msg or 'visitor' in msg:
        return f"Demo data shows {store} averages about 120 donor visits per day, with weekends seeing up to 250 visits. Peak hours are typically 10am-2pm on Saturdays."
    elif 'compare' in msg or 'best' in msg or 'worst' in msg:
        return "In demo mode, the Fredericksburg Rd location leads with the highest net revenue, while Bandera Rd shows the strongest growth trend. Connect to your SQL Server for actual comparisons."
    elif 'manager' in msg:
        return "GWSA locations are supported by store managers and regional leaders, but this demo does not expose individual manager names."
    else:
        return f"I'm the GWSA GeoAnalytics AI assistant running in demo mode. I can help analyze store performance, door counts, revenue trends, and compare locations. Configure Azure OpenAI in backend/.env for full AI capabilities. Try asking about revenue, door counts, or store comparisons!"
