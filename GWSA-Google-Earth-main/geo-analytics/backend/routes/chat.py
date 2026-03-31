"""
GWSA GeoAnalytics — Gemini AI Chat Route
POST /api/chat — proxies to Google Gemini (key never in browser)
"""
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from middleware.security import limiter, ChatRequestSchema, is_safe_sql
from config import Config

chat_bp = Blueprint('chat', __name__)

SYSTEM_CONTEXT = """
You are a data analyst assistant for Goodwill Industries of San Antonio (GWSA)
You have access to store financial data, POS / line-level daily sales, door counts, and location
information across San Antonio, South Texas, and Laredo. Be concise, professional, and data-driven.
Store types: retail stores, ADC (Attended Donation Centers), outlets, drop boxes.
Do not mention or infer specific manager names; refer only to roles (for example, "store managers" or "regional leaders").
When providing numbers, use proper currency formatting ($X,XXX).
For store-level sales, the authoritative line table includes Revenue, Soldts (transaction time),
SalesCategoryFromGP (filter 'Core Sales' for core retail revenue), SoldStoreId, and [sales unit name]
(store display name). Ignore columns not listed in the schema hint unless the user asks.
"""


def _get_gemini_model():
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception:
        return None


def try_text_to_sql(model, question: str, store_id: str):
    """Attempt to generate and execute a safe SQL query from natural language."""
    # Object name matches Config.SQL_SALES_LINE_OBJECT (default JS_API.dbo.SalesFactFinal)
    schema_hint = """
    Tables:
      Locations(LocationID, LocationName, LocationType, Manager)
      PeopleCounter.dbo.PCounter(LocationID, Date, In; hourly rows aggregate to daily; multiple LocationIDs per store sum Left+Right)
      SalesFactFinal (JS_API.dbo — line-level POS; primary source for revenue KPIs):
        SalesTransid, SalesLineNum, SoldStoreId, SKU, Qty, DetailPrice, DetailTotalDiscount, DetailTax,
        RotColor, Category, Subcategory, Dept, Soldts (DATETIME — filter by date for MTD),
        PricePoint, CashEmp, Register, Transtype, OrigTrans, OrigStoreId, ttlSaleTax, ttlNetTotalPrice,
        Revenue (line revenue; SUM for MTD Core Sales),
        [sales unit name] (store display name),
        SalesSubCategoryFromGP, SalesCategoryFromGP (use N'Core Sales' for core retail revenue)
      Ignore for current KPIs: Unit, [sales store unit], DiscountType, barcode, Vena_Groups, DGR_Tiers, SalesAccount.
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

    # Demo mode fallback when no Gemini key
    model = _get_gemini_model()
    if not model or not Config.GEMINI_API_KEY:
        return jsonify({
            'reply': _demo_reply(user_message, store_context),
            'sql_used': None,
            'data': None
        })

    context = SYSTEM_CONTEXT
    if store_context:
        context += f"\nUser is viewing: '{store_context}' location."

    # Attempt text-to-SQL for data questions
    sql_result, sql_used = None, None
    data_kws = ['highest', 'lowest', 'compare', 'trend', 'revenue',
                'income', 'door count', 'best', 'worst', 'total',
                'average', 'sum', 'how many', 'which store']
    if any(kw in user_message.lower() for kw in data_kws):
        sql_used, sql_result = try_text_to_sql(model, user_message, store_context)

    full_prompt = context
    if sql_result:
        full_prompt += f"\n\nRelevant DB data:\n{sql_result}"
    full_prompt += f"\n\nUser question: {user_message}"

    try:
        response = model.generate_content(full_prompt)
        return jsonify({
            'reply': response.text,
            'sql_used': sql_used,
            'data': sql_result
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
