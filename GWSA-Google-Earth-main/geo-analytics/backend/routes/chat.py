"""
GWSA GeoAnalytics — Gemini AI Chat Route
POST /api/chat — proxies to Google Gemini (key never in browser)
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


def _get_gemini_model():
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-1.5-flash')
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


def _plan_request(model, user_message: str, store_context: str, history: list) -> dict:
    """Have the model choose from a small set of approved analytics actions."""
    from db.queries import get_location_catalog

    catalog = get_location_catalog(limit=60)
    planning_prompt = f"""
You are an intent router for GWSA GeoAnalytics.
Choose one approved action only when the question clearly matches it.

Allowed actions:
- none
- location_summary
- compare_locations
- rank_locations

Allowed metrics:
- revenue
- door_count

Rules:
- Use only the location names provided in the catalog.
- use_viewing_store should be true only when the current viewed location is relevant.
- compare_locations requires two store names.
- rank_locations is for questions like "highest", "best", "top", or "which store has the most".
- location_summary is for a single store's performance summary.
- If uncertain, return action "none".
- Return JSON only. No markdown.

Current viewed location: {store_context or "none"}
Recent conversation:
{_history_to_text(history) or "none"}

Location catalog:
{json.dumps(catalog)}

User question:
{user_message}

Return exactly this JSON shape:
{{
  "action": "none",
  "metric": "revenue",
  "store_names": [],
  "use_viewing_store": false,
  "limit": 5
}}
"""
    try:
        response = model.generate_content(planning_prompt)
        plan = _extract_json_object(getattr(response, "text", ""))
    except Exception:
        plan = {}

    action = plan.get("action", "none")
    metric = plan.get("metric", "revenue")
    store_names = plan.get("store_names") if isinstance(plan.get("store_names"), list) else []
    limit = plan.get("limit", 5)

    if action not in INTENT_ACTIONS:
        action = "none"
    if metric not in INTENT_METRICS:
        metric = "revenue"

    cleaned_names = []
    for name in store_names[:2]:
        value = str(name).strip()
        if value:
            cleaned_names.append(value[:80])

    try:
        parsed_limit = int(limit)
    except (TypeError, ValueError):
        parsed_limit = 5

    return {
        "action": action,
        "metric": metric,
        "store_names": cleaned_names,
        "use_viewing_store": bool(plan.get("use_viewing_store")),
        "limit": max(1, min(parsed_limit, 10)),
    }


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
    prompt = SYSTEM_CONTEXT
    if store_context:
        prompt += f"\nCurrent viewed location: {store_context}."
    if data_action and data:
        prompt += f"\nApproved analytics action used: {data_action}."
        prompt += f"\nStructured analytics data:\n{json.dumps(data, indent=2)}"
    prompt += f"\n\nUser question: {user_message}"
    return prompt


@chat_bp.route('/api/chat', methods=['POST'])
@limiter.limit("10 per minute")
def chat():
    schema = ChatRequestSchema()
    try:
        data = schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        return jsonify(error=err.messages), 400

    user_message = data['message']
    store_context = data.get('store_context')
    history = data.get('conversation_history', [])

    model = _get_gemini_model()
    if not model or not Config.GEMINI_API_KEY:
        return jsonify({
            'reply': _demo_reply(user_message, store_context),
            'sql_used': None,
            'data': None
        })

    plan = _plan_request(model, user_message, store_context, history)
    data_action, analytics_data = _execute_approved_action(plan, store_context)
    full_prompt = _build_response_prompt(user_message, store_context, data_action, analytics_data)

    try:
        response = model.generate_content(full_prompt)
        return jsonify({
            'reply': response.text,
            'sql_used': data_action,
            'data': analytics_data
        })
    except Exception as e:
        return jsonify(error=f"AI service error: {str(e)}"), 500


def _demo_reply(message: str, store_context: str = None) -> str:
    """Provide helpful demo responses when Gemini API key is not configured."""
    msg = message.lower()
    store = store_context or "the selected location"

    if 'revenue' in msg or 'income' in msg:
        return f"Based on demo data for {store}, this location shows average monthly net revenue of approximately $145,000 with a healthy expense ratio around 68%. To see live data, configure your Gemini API key and SQL Server connection."
    elif 'door count' in msg or 'visitor' in msg:
        return f"Demo data shows {store} averages about 120 donor visits per day, with weekends seeing up to 250 visits. Peak hours are typically 10am-2pm on Saturdays."
    elif 'compare' in msg or 'best' in msg or 'worst' in msg:
        return "In demo mode, the Fredericksburg Rd location leads with the highest net revenue, while Bandera Rd shows the strongest growth trend. Connect to your SQL Server for actual comparisons."
    elif 'manager' in msg:
        return "GWSA locations are supported by store managers and regional leaders, but this demo does not expose individual manager names."
    else:
        return f"I'm the GWSA GeoAnalytics AI assistant running in demo mode. I can help analyze store performance, door counts, revenue trends, and compare locations. Configure your GEMINI_API_KEY in backend/.env for full AI capabilities. Try asking about revenue, door counts, or store comparisons!"
