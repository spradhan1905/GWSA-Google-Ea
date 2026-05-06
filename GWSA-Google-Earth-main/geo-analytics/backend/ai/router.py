"""Map a typed plan to approved DB retrieval (no LLM)."""
from db.analytics_actions import execute_approved_action


def run_retrieval(plan: dict, store_context: str):
    """Execute the plan via analytics_actions."""
    return execute_approved_action(plan, store_context)
