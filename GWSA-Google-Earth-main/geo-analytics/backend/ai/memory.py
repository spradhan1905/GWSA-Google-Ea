"""Lightweight conversation context for the composer (session state can extend this)."""


def summarize_history(history: list, max_turns: int = 6) -> str:
    """Compact recent turns for the user prompt (not sent as separate chat roles)."""
    lines = []
    for item in history[-max_turns:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    if not lines:
        return "(no prior turns in this session summary)"
    return "\n".join(lines)
