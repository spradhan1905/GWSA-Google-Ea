"""Build LLM prompts/messages and manage provider clients."""
import json
from typing import List, Optional

from config import Config

from ai.memory import summarize_history
from ai.prompts import SYSTEM_CONTEXT


def azure_openai_configured() -> bool:
    return all([
        Config.AZURE_OPENAI_ENDPOINT,
        Config.AZURE_OPENAI_API_KEY,
        Config.AZURE_OPENAI_DEPLOYMENT,
        Config.AZURE_OPENAI_API_VERSION,
    ])


def get_azure_openai_client():
    try:
        from openai import AzureOpenAI
        from urllib.parse import urlparse

        parsed_endpoint = urlparse(Config.AZURE_OPENAI_ENDPOINT)
        if parsed_endpoint.scheme and parsed_endpoint.netloc:
            host = parsed_endpoint.netloc.replace(
                ".cognitiveservices.azure.com",
                ".openai.azure.com",
            )
            azure_endpoint = f"{parsed_endpoint.scheme}://{host}"
        else:
            azure_endpoint = Config.AZURE_OPENAI_ENDPOINT

        return AzureOpenAI(
            api_key=Config.AZURE_OPENAI_API_KEY,
            azure_endpoint=azure_endpoint,
            api_version=Config.AZURE_OPENAI_API_VERSION,
        )
    except Exception:
        return None


def get_gemini_model():
    try:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        return genai.GenerativeModel(Config.GEMINI_MODEL)
    except Exception:
        return None


def build_response_prompt(
    user_message: str,
    store_context: Optional[str],
    history: list,
    data_action: Optional[str],
    data: Optional[dict],
    data_gap_description: str,
) -> str:
    """User turn content matching GWSA_AI_MODEL.md evidence contract."""
    dashboard = (store_context or "").strip() or "(none selected)"
    memory_summary = summarize_history(history)
    action_label = data_action if data_action else "(none)"

    blocks = [
        f"Current dashboard context:\n{dashboard}\n",
        f"Conversation memory:\n{memory_summary}\n",
        f"Approved analytics action:\n{action_label}\n",
    ]

    if data_action and data:
        blocks.append(f"Retrieved evidence:\n{json.dumps(data, indent=2)}\n")
        if data.get("grain") == "day" and data.get("periods") == []:
            blocks.append(
                "The periods list is empty: no daily aggregate rows were returned for this metric, "
                "scope, and date range. Say so clearly; do not substitute location-level monthly totals.\n",
            )
    elif data_action and not data:
        blocks.append("Retrieved evidence:\n(null)\n")
    else:
        blocks.append("Retrieved evidence:\n(none)\n")

    blocks.append(f"Data gaps:\n{data_gap_description}\n")
    blocks.append(f"User question:\n{user_message}")
    return "\n".join(blocks)


def build_azure_messages(
    user_message: str,
    store_context: Optional[str],
    history: list,
    data_action: Optional[str],
    data: Optional[dict],
    data_gap_description: str,
) -> List[dict]:
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
        "content": build_response_prompt(
            user_message,
            store_context,
            history,
            data_action,
            data,
            data_gap_description,
        ),
    })
    return messages


def build_gemini_user_text(
    user_message: str,
    store_context: Optional[str],
    history: list,
    data_action: Optional[str],
    data: Optional[dict],
    data_gap_description: str,
) -> str:
    return build_response_prompt(
        user_message,
        store_context,
        history,
        data_action,
        data,
        data_gap_description,
    )
