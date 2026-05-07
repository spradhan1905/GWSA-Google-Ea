"""Build LLM prompts/messages and manage provider clients (V3 composer)."""
from __future__ import annotations

import json
from typing import Any, List, Optional

from config import Config

from ai.composer_prompt import COMPOSER_SYSTEM_PROMPT
from ai.context import trim_evidence
from ai.memory import SessionState, build_memory_context

_MAX_EVIDENCE_CHARS = 3000
_CHAT_HISTORY_MESSAGES = 3


def _fmt_metric_amount(metric: str, value: Any) -> str:
    if value is None:
        return "n/a"
    m = (metric or "").strip().lower()
    try:
        if m == "door_count":
            return f"{int(round(float(value))):,}"
        if m in {"expense_ratio"}:
            return str(round(float(value), 4))
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _humanize_evidence(data: dict) -> dict:
    """Rename machine-oriented keys so the model is less likely to echo them verbatim."""
    if not isinstance(data, dict):
        return data
    out: dict = {}
    for key, value in data.items():
        new_key = key
        if key == "leader":
            new_key = "top_result"
        elif key == "metric_value":
            new_key = "amount"
        elif key == "location_name":
            new_key = "store"
        elif key == "location_id":
            new_key = "store_id"
        elif key == "metric":
            new_key = "measure"
        if isinstance(value, dict):
            out[new_key] = _humanize_evidence(value)
        elif isinstance(value, list):
            out[new_key] = [
                _humanize_evidence(v) if isinstance(v, dict) else v for v in value
            ]
        else:
            out[new_key] = value
    return out


def _trim_for_llm(data: dict) -> dict:
    """Drop noisy fields and cap long lists before JSON serialization."""
    if not isinstance(data, dict):
        return data
    drop_keys = {"source", "sql_used", "scope", "_series_truncated_note", "_locations_truncated_note"}
    out = {k: v for k, v in data.items() if k not in drop_keys}
    for key in ("series", "periods", "locations", "rows", "top_store_days"):
        if key in out and isinstance(out[key], list) and len(out[key]) > 10:
            raw_len = len(out[key])
            out[key] = out[key][:10]
            out[f"_{key}_note"] = f"Showing top 10 of {raw_len} total"
    return out


def _cap_evidence_chars(text: str) -> str:
    if len(text) <= _MAX_EVIDENCE_CHARS:
        return text
    return (
        text[: _MAX_EVIDENCE_CHARS - 80]
        + "\n… (remainder omitted to keep response fast).\n"
    )


def evidence_to_natural_language(data_action: Optional[str], data: dict) -> str:
    """Turn approved analytics payloads into prose the composer can narrate from (V3)."""
    da = data_action or ""
    if not isinstance(data, dict) or not data:
        return "No structured data was retrieved."

    metric_key = str(data.get("metric") or "revenue")
    metric = metric_key.replace("_", " ")
    tf = data.get("timeframe") if isinstance(data.get("timeframe"), dict) else {}
    period = str(tf.get("label") or "").strip()
    if not period and tf.get("start") and tf.get("end"):
        period = f"{tf.get('start')} through {tf.get('end')}"

    if da.startswith("compare_locations:"):
        locs = data.get("locations") or []
        if len(locs) >= 2:
            a, b = locs[0], locs[1]
            ma = float(a.get("metric_value")) if a.get("metric_value") is not None else None
            mb = float(b.get("metric_value")) if b.get("metric_value") is not None else None
            an = _fmt_metric_amount(metric_key, ma)
            bn = _fmt_metric_amount(metric_key, mb)
            na = str(a.get("location_name") or "").strip()
            nb = str(b.get("location_name") or "").strip()
            if ma is not None and mb is not None and ma >= mb:
                hi, hi_n, lo, lo_n = na, an, nb, bn
                diff_txt = ""
                try:
                    diff = ma - mb
                    if metric_key == "door_count":
                        diff_txt = f" ({int(round(diff)):,} higher than {nb}.)"
                    else:
                        diff_txt = f" (${diff:,.2f} ahead of {nb}.)"
                except Exception:
                    diff_txt = ""
            elif ma is not None and mb is not None:
                hi, hi_n, lo, lo_n = nb, bn, na, an
                try:
                    diff = mb - ma
                    if metric_key == "door_count":
                        diff_txt = f" ({int(round(diff)):,} higher than {na}.)"
                    else:
                        diff_txt = f" (${diff:,.2f} ahead of {na}.)"
                except Exception:
                    diff_txt = ""
            else:
                hi, hi_n, lo, lo_n = na, an, nb, bn
                diff_txt = ""
            period_bit = f"For {period}, " if period else ""
            core = metric_key.replace("_", " ")
            return _cap_evidence_chars(
                f"{period_bit}{hi} recorded {hi_n} in {core} compared with {lo} at {lo_n}.{diff_txt} "
                f"Treat these as authoritative figures for answering the user's question."
            )
        return "Comparison data returned fewer than two locations."

    if da.startswith("rank_locations:") or da.startswith("metric_breakdown:"):
        locs = list(data.get("locations") or [])[:10]
        if not locs:
            return _cap_evidence_chars(
                json.dumps(_trim_for_llm(_humanize_evidence(data)), separators=(",", ":"), ensure_ascii=False, default=str)
            )
        ranked_phrases = []
        for i, loc in enumerate(locs, 1):
            nm = str(loc.get("location_name") or "").strip()
            amt = loc.get("metric_value")
            ranked_phrases.append(f"#{i} is {nm} at {_fmt_metric_amount(metric_key, amt)}")
        period_bit = f" during {period}" if period else ""
        prose = (
            f"Ranking by {metric}{period_bit}: "
            + "; ".join(ranked_phrases)
            + ". Use exact numbers only from this ranking."
        )
        return _cap_evidence_chars(prose)

    if da.startswith("rank_periods"):
        periods = list(data.get("periods") or [])
        mkey = str(data.get("metric") or "revenue")
        metric_label = mkey.replace("_", " ")
        scope = str(data.get("scope") or "").strip()
        loc_nm = str(data.get("location_name") or "").strip()
        preamble = ""
        if scope == "location" and loc_nm:
            if mkey == "door_count":
                preamble = (
                    f"Single-store ranking (daily donor visits) for {loc_nm}. "
                    "Do not describe these totals as network-wide sums. "
                )
            else:
                preamble = (
                    f"Single-store ranking (daily core revenue) for {loc_nm}. "
                    "Do not describe these totals as network-wide sums. "
                )
        elif scope == "all_retail_stores":
            if mkey == "door_count":
                preamble = (
                    "Network-wide ranking: donor visits are summed across all scoped retail stores per calendar day. "
                    "Do not attribute these totals to one store unless a store name appears in evidence. "
                )
            else:
                preamble = (
                    "Network-wide ranking: amounts are summed across all scoped retail stores per calendar day "
                    "(daily core revenue). "
                    "Do not attribute these daily totals to one store unless a store name appears in evidence. "
                )
        if periods:
            parts = []
            for i, p in enumerate(periods[:10], 1):
                d = str(p.get("date") or "").strip()
                mv = p.get("metric_value")
                if mkey == "door_count":
                    parts.append(f"{d} saw {_fmt_metric_amount('door_count', mv)} visits (rank #{i})")
                else:
                    parts.append(f"{d} had core sales around {_fmt_metric_amount('revenue', mv)} (rank #{i})")
            period_bit = f"within {period}" if period else "in the requested range"
            prose = (
                preamble
                + f"Daily picture for {metric_label} {period_bit}: "
                + "; ".join(parts)
                + "."
            )
            return _cap_evidence_chars(prose)
        return _cap_evidence_chars(
            f"No daily rows were returned for {metric_label} "
            + (f"in {period}." if period else "for that question.")
        )

    if da == "peak_store_daily_revenue":
        top = data.get("top_store_days") or []
        if top:
            best = top[0]
            nm = str(best.get("location_name") or "").strip()
            dk = str(best.get("date") or "").strip()
            mv = best.get("metric_value")
            period_bit = period or "that period"
            return _cap_evidence_chars(
                f"The strongest single store day for core revenue in {period_bit} was {nm} on {dk}, "
                f"at about {_fmt_metric_amount('revenue', mv)}. Cite those values exactly."
            )
        period_bit = period or "the requested dates"
        return _cap_evidence_chars(f"No daily revenue peak rows were returned for {period_bit}.")

    if da.startswith("location_summary:") or da == "location_summary":
        name = str(data.get("location_name") or data.get("name") or "").strip()
        mets = data.get("metrics") or {}
        extras = ""
        rows = data.get("rows") or []
        if isinstance(rows, list) and rows:
            extras = f" The payload includes {len(rows)} daily rows summarizing totals for the stated window."
        return _cap_evidence_chars(
            f"Summary for {name or 'selected store'}: key metrics snapshot {dict(mets) if mets else 'is attached'}.{extras}"
        )

    if da.startswith("trend_summary"):
        name = str(data.get("location_name") or "").strip()
        rows = data.get("rows") or []
        return _cap_evidence_chars(
            f"Trend buckets for {name or 'selected store'}: {len(rows)} rows (most recent buckets last); "
            f"use exact NetRevenue and DoorCount figures from those rows."
        )

    trimmed = _trim_for_llm(_humanize_evidence(data))
    return _cap_evidence_chars(
        json.dumps(trimmed, separators=(",", ":"), ensure_ascii=False, default=str)
    )


def _evidence_json(data: dict) -> str:
    """Compact JSON for fallback evidence blocks."""
    base = trim_evidence(data) if isinstance(data, dict) else data
    packed = json.dumps(base, separators=(",", ":"), ensure_ascii=False, default=str)
    return _cap_evidence_chars(packed)


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


def build_composer_messages(
    user_message: str,
    session: SessionState,
    plan: dict,
    data_action: Optional[str],
    analytics_data: Optional[dict],
    data_gap: str,
    history: list,
) -> List[dict]:
    """Azure OpenAI composer: system + trimmed history + natural-language evidence."""
    system = COMPOSER_SYSTEM_PROMPT
    memory_context = build_memory_context(session, history, max_turns=4)
    dash = session.selected_store_name or "(none)"

    evidence_block = ""
    if data_action and analytics_data:
        evidence_block = evidence_to_natural_language(data_action, analytics_data)
        if evidence_block.startswith("No structured data") or evidence_block.startswith("Comparison data returned fewer"):
            evidence_block = _evidence_json(_trim_for_llm(_humanize_evidence(analytics_data)))
        if (
            analytics_data.get("grain") == "day"
            and not (analytics_data.get("periods") or [])
        ):
            evidence_block += (
                " Note: the daily-period list was empty—do not recast monthly store totals "
                "as if they answered a single-day question."
            )
    elif data_action and not analytics_data:
        evidence_block = "The approved query executed but produced no usable rows."
    else:
        evidence_block = "No structured analytics accompanied this prompt."

    lim = data_gap.strip() if data_gap and data_gap.strip() not in {"", "None."} else ""
    limitation = f"\nLimitation noted for you: {lim}" if lim else ""

    user_content = "\n\n".join(
        [
            f"The user’s dashboard anchor store is {dash}. "
            f"Use the prose figures below—they are authoritative for this reply.",
            f"Conversation recap:\n{memory_context}",
            f"Facts to weave into fluent sentences:\n{evidence_block}{limitation}",
            f"The user asked: {user_message}",
        ]
    )

    messages: List[dict] = [{"role": "system", "content": system}]
    for item in (history or [])[-_CHAT_HISTORY_MESSAGES:]:
        role = item.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": str(item.get("content", ""))[:500]})
    messages.append({"role": "user", "content": user_content})
    return messages


def build_response_prompt(
    user_message: str,
    store_context: Optional[str],
    history: list,
    data_action: Optional[str],
    data: Optional[dict],
    data_gap_description: str,
) -> str:
    """Legacy single-block prompt (dashboard + recap + prose evidence + question)."""
    dash = (store_context or "").strip() or "(none selected)"
    memory_summary = build_memory_context(SessionState(), history, max_turns=4)

    parts = [f"The user is viewing dashboard context: {dash}."]
    parts.append(f"Conversation recap:\n{memory_summary}".strip())

    if data_action and data:
        ev = evidence_to_natural_language(data_action, data)
        if ev.startswith("No structured"):
            ev = _evidence_json(_trim_for_llm(_humanize_evidence(data)))
        parts.append(f"Facts to weave into fluent sentences:\n{ev}")
        if data.get("grain") == "day" and not (data.get("periods") or []):
            parts.append(
                "Note: empty daily-period list—do not pretend monthly aggregates are daily answers."
            )
    elif data_action and not data:
        parts.append("The retrieval query returned nothing usable.")
    else:
        parts.append("No retrieval evidence was tied to this request.")

    dg = data_gap_description.strip()
    if dg and dg not in {"None.", ""}:
        parts.append(f"Limitation for the composer: {dg}")

    parts.append(f"The user asked:\n{user_message}")
    return "\n\n".join(parts)


def build_azure_messages(
    user_message: str,
    store_context: Optional[str],
    history: list,
    data_action: Optional[str],
    data: Optional[dict],
    data_gap_description: str,
) -> List[dict]:
    """Compatibility wrapper that builds composer messages without session slots."""
    sess = SessionState()
    return build_composer_messages(
        user_message,
        sess,
        {},
        data_action,
        data,
        data_gap_description,
        history,
    )
