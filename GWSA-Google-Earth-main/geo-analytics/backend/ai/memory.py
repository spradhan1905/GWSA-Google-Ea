"""Session memory for V2 chat: store/metric/timeframe carry-forward and reference resolution."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional


@dataclass
class SessionState:
    selected_store: Optional[str] = None
    selected_store_name: Optional[str] = None
    last_metric: Optional[str] = None
    last_timeframe: Optional[dict] = None
    last_intent: Optional[str] = None
    last_data_action: Optional[str] = None
    last_store_names: List[str] = field(default_factory=list)
    pending_followups: List[str] = field(default_factory=list)
    turn_count: int = 0

    def to_context_string(self) -> str:
        parts: List[str] = []
        if self.selected_store_name:
            parts.append(f"Selected store: {self.selected_store_name}")
        if self.last_metric:
            parts.append(f"Last metric: {self.last_metric}")
        if self.last_timeframe:
            lbl = ""
            if isinstance(self.last_timeframe, dict):
                lbl = str(self.last_timeframe.get("label") or "")
            parts.append(f"Last timeframe: {lbl}")
        if self.last_intent:
            parts.append(f"Last intent: {self.last_intent}")
        if self.pending_followups:
            preview = "; ".join(self.pending_followups[:3])
            parts.append(f"Pending follow-up suggestions: {preview}")
        return "; ".join(parts) if parts else "(no session context)"

    @classmethod
    def from_payload(cls, data: Optional[dict]) -> "SessionState":
        if not data or not isinstance(data, dict):
            return cls()
        ls = data.get("last_store_names") or []
        pf = data.get("pending_followups") or []
        return cls(
            selected_store=data.get("selected_store"),
            selected_store_name=data.get("selected_store_name"),
            last_metric=data.get("last_metric"),
            last_timeframe=data.get("last_timeframe"),
            last_intent=data.get("last_intent"),
            last_data_action=data.get("last_data_action"),
            last_store_names=[str(x) for x in ls if x][:10],
            pending_followups=[str(x) for x in pf if x][:12],
            turn_count=int(data.get("turn_count") or 0),
        )

    def to_payload(self) -> dict:
        return {k: v for k, v in asdict(self).items()}


@dataclass
class ResolvedQuery:
    """Enriched text the planner/composer should use."""

    text: str
    from_pending_followup: bool = False


def _is_short_affirmation(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t or len(t) > 120:
        return False
    return bool(
        re.match(
            r"^(?:\s*(?:ok+|okay|sure|yeah|yep|yes|please)\b[\s,!,.]*)+"
            r'|^\s*(?:go ahead|do (?:it|that)|sounds good|that works|fine)\b'
            r"|\s*(?:show (?:me )?that|show the trend)\s*[!.]*\s*$",
            t,
            re.I,
        )
    )


def resolve_references(
    user_message: str,
    session: SessionState,
    store_context: Optional[str],
) -> ResolvedQuery:
    """
    Resolve pronouns and implicit references before the planner runs.
    If the user accepts a follow-up chip, substitute that question as the effective user text.
    """
    text = (user_message or "").strip()
    low = text.lower()

    if session.pending_followups and _is_short_affirmation(text):
        return ResolvedQuery(text=session.pending_followups[0], from_pending_followup=True)

    extras: List[str] = []

    if session.selected_store_name and any(
        k in low for k in ("this store", "selected store", "the selected store", "that store", "here ")
    ):
        extras.append(f"[Context: user refers to map-selected store '{session.selected_store_name}'.]")

    if store_context and str(store_context).strip():
        extras.append(f"[Dashboard store_context id: {str(store_context).strip()}]")

    if session.last_timeframe and re.match(
        r"^(what about|how about)\s+", low
    ):
        lbl = ""
        if isinstance(session.last_timeframe, dict):
            lbl = str(session.last_timeframe.get("label") or "")
        if lbl:
            extras.append(f"[Keep prior timeframe unless user overrides: {lbl}.]")

    if session.last_metric and "door" in low and "compare" not in low:
        extras.append("[User may be changing metric; prior metric was: {}.]".format(session.last_metric))

    follow_triggers = (
        "categor", "category", "both", "them", "those two", "the two", "same stores",
        "add door", "door count", "same period", "same month", "chart", "graph",
        "visualize", "plot", "go deeper", "more detail", "donations for",
        "expense ratio", "revenue per visitor", "per visitor", "instead",
        "monthly trend", "show me which", "explain the gap", "break down",
        "compare them", "compare those", "for both", "for them", "what about",
        "now show", "now add", "put that in", "full paragraph", "overview",
    )
    if session.last_store_names and any(tok in low for tok in follow_triggers):
        names = ", ".join(session.last_store_names[:3])
        extras.append(
            f"[Follow-up: continue with the same store(s) from the prior turn: {names}. "
            "Reuse the prior month/date range unless the user overrides it.]"
        )

    if session.last_timeframe and isinstance(session.last_timeframe, dict):
        if any(tok in low for tok in ("same month", "same period", "that period", "for may instead", "for march instead")):
            lbl = session.last_timeframe.get("label") or ""
            if lbl:
                extras.append(f"[Default timeframe from prior turn: {lbl}.]")

    if extras:
        text = text + "\n" + "\n".join(extras)

    return ResolvedQuery(text=text, from_pending_followup=False)


def build_memory_context(session: SessionState, history: list, max_turns: int = 4) -> str:
    """Structured summary for the composer (includes session slots + recent turns)."""
    lines: List[str] = []
    if session.last_store_names:
        lines.append(f"Previously discussed store: {session.last_store_names[0]}")
    if session.selected_store_name:
        lines.append(f"Active store: {session.selected_store_name}")
    if session.last_metric:
        lines.append(f"Last metric discussed: {session.last_metric}")
    if session.last_timeframe and isinstance(session.last_timeframe, dict):
        lines.append(f"Last timeframe: {session.last_timeframe.get('label', '')}")
    lines.append("")
    for item in (history or [])[-max_turns:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content[:300]}")
    return "\n".join(lines) if lines else "(new conversation)"


def merge_session_after_turn(
    session: SessionState,
    plan: dict,
    data_action: Optional[str],
    store_context: Optional[str],
) -> None:
    """Update mutable session fields after a successful plan (before reply)."""
    session.turn_count = int(session.turn_count or 0) + 1
    if plan.get("intent"):
        session.last_intent = plan.get("intent")
    if plan.get("metric"):
        session.last_metric = plan.get("metric")
    if plan.get("timeframe"):
        session.last_timeframe = plan.get("timeframe")
    if data_action:
        session.last_data_action = data_action
    names = plan.get("store_names") or []
    if names:
        session.last_store_names = [str(n) for n in names[:3]]
    if store_context and str(store_context).strip():
        session.selected_store = str(store_context).strip()
        from db.queries import resolve_location_reference

        loc = resolve_location_reference(str(store_context).strip())
        if loc:
            session.selected_store_name = str(loc.get("LocationName") or "") or session.selected_store_name


def set_pending_followups(session: SessionState, followups: List[str]) -> None:
    session.pending_followups = [str(f).strip() for f in (followups or []) if str(f).strip()][:10]
