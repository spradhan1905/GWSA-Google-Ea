"""
Curated user question bank (300) for planner hints, data catalog, and QA.
Source: docs/AI_USER_QUESTION_BANK.md (v1) + generated v2 prompts.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_PATH = Path(__file__).resolve().parent / "data" / "question_bank.json"


@lru_cache(maxsize=1)
def load_question_bank() -> Dict[str, Any]:
    if not _DATA_PATH.is_file():
        return {"version": 0, "total": 0, "questions": []}
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def all_questions() -> List[Dict[str, Any]]:
    return list(load_question_bank().get("questions") or [])


def questions_by_tag(tag: str, limit: int = 50) -> List[str]:
    out = []
    for q in all_questions():
        if tag in (q.get("tags") or []):
            out.append(str(q.get("text") or "").strip())
            if len(out) >= limit:
                break
    return out


def questions_by_category(category: str, limit: int = 50) -> List[str]:
    out = []
    for q in all_questions():
        if q.get("category") == category:
            out.append(str(q.get("text") or "").strip())
            if len(out) >= limit:
                break
    return out


def sample_questions_for_catalog(limit: int = 24) -> List[str]:
    """Representative prompts surfaced when users ask what the assistant can do."""
    bank = all_questions()
    if not bank:
        return []
    picks: List[str] = []
    seen_cats = set()
    for q in bank:
        cat = q.get("category") or "general"
        if cat in seen_cats and len(picks) < limit - 8:
            continue
        text = str(q.get("text") or "").strip()
        if text and text not in picks:
            picks.append(text)
            seen_cats.add(cat)
        if len(picks) >= limit:
            break
    if len(picks) < limit:
        for q in bank:
            text = str(q.get("text") or "").strip()
            if text and text not in picks:
                picks.append(text)
            if len(picks) >= limit:
                break
    return picks[:limit]


def planner_pattern_summary() -> str:
    """Compact pattern list injected into the LLM planner system prompt."""
    cats = {}
    for q in all_questions():
        c = q.get("category") or "general"
        cats.setdefault(c, 0)
        cats[c] += 1
    lines = [
        "## User question patterns (300-example bank; classify into intents above)",
        "- compare_revenue: two+ stores, same month/range, core sales/revenue",
        "- category_breakdown: revenue Category/RevenueType mix, gaps between stores, 'what drove'",
        "- follow_up: short prompts after a compare ('add door count', 'show categories', 'chart it') — reuse session stores/timeframe",
        "- charts: user says graph/chart/visualize/plot",
        "- store_overview: 'how is X doing', full summary, deep dive, leadership brief",
        "- rankings / donations_door / budget_periods / trends / key_metrics: as labeled",
        f"- Bank size: {load_question_bank().get('total', 0)} exemplar questions across {len(cats)} categories",
    ]
    examples = []
    for tag, label in (
        ("category", "Category"),
        ("follow_up", "Follow-up"),
        ("chart", "Chart"),
        ("detail", "Detailed"),
    ):
        for text in questions_by_tag(tag, limit=2):
            examples.append(f"  • [{label}] {text[:120]}")
    if examples:
        lines.append("Sample phrasing:")
        lines.extend(examples[:10])
    return "\n".join(lines)


def match_question_intent_hint(user_message: str) -> Optional[str]:
    """Lightweight hint for heuristics when phrasing matches the bank."""
    t = (user_message or "").lower().strip()
    if not t:
        return None
    if any(x in t for x in ("categor", "revenue type", "line item", "subcategory", "mix", "what drove", "contributing")):
        return "category_breakdown"
    if any(x in t for x in ("graph", "chart", "visualize", "plot", "draw a")):
        return "compare_locations"  # often with requires_chart
    if any(x in t for x in ("full overview", "deep dive", "brief", "explain", "why ", "root cause", "talking points")):
        return "multi_metric_summary"
    if t in ("more detail pls", "more detail", "i need more than one sentence", "break it down by category"):
        return "follow_up"
    return None
