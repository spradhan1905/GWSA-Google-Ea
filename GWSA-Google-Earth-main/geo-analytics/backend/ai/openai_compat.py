"""Azure OpenAI chat completion parameter compatibility (max_tokens vs max_completion_tokens)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from config import Config


def _deployment_uses_max_completion_tokens() -> bool:
    """
    Newer Azure deployments (o-series, gpt-5.x, etc.) reject max_tokens and require
    max_completion_tokens instead.
    """
    explicit = (getattr(Config, "AZURE_OPENAI_USE_MAX_COMPLETION_TOKENS", None))
    if explicit is not None:
        return bool(explicit)
    dep = (Config.AZURE_OPENAI_DEPLOYMENT or "").lower()
    needles = ("o1", "o3", "o4", "gpt-5", "gpt5", "reasoning")
    return any(n in dep for n in needles)


def completion_token_kwargs(
    limit: Optional[int] = None,
    *,
    prefer_max_completion_tokens: Optional[bool] = None,
) -> Dict[str, Any]:
    """Return only the token-limit key supported by the configured deployment."""
    if limit is None:
        return {}
    use_mct = (
        prefer_max_completion_tokens
        if prefer_max_completion_tokens is not None
        else _deployment_uses_max_completion_tokens()
    )
    if use_mct:
        return {"max_completion_tokens": int(limit)}
    return {"max_tokens": int(limit)}


def merge_chat_completion_kwargs(base: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    """
    Merge kwargs for client.chat.completions.create, normalizing token limit keys.
    Pass limit via max_tokens= or max_completion_tokens= in extra (not both).
    """
    out = dict(base)
    out.update(extra)
    limit = out.pop("max_completion_tokens", None)
    if limit is None:
        limit = out.pop("max_tokens", None)
    if limit is not None:
        out.update(completion_token_kwargs(int(limit)))
    return out
