"""Approved analytics retrieval — thin dispatcher over parameterized SQL helpers."""
from typing import Any, Optional, Tuple

from db.analytics_actions import execute_approved_action


def run_retrieval(plan: dict, store_context: str) -> Tuple[Optional[str], Any]:
    """
    Run the validated execution plan.

    Caller should apply ``coerce_plan_for_daily_peak_questions`` to ``plan`` when the user's
    message is available (done in routes/chat.py).
    """
    return execute_approved_action(plan, store_context or "")
