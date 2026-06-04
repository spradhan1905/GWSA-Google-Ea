"""Build backend/ai/data/question_bank.json (300 user questions). Run from repo root."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT.parent / "docs" / "AI_USER_QUESTION_BANK.md"
OUT = ROOT / "ai" / "data" / "question_bank.json"

TAG_MAP = {
    "Detail": "detail",
    "Chart": "chart",
    "Category": "category",
    "FOLLOW-UP": "follow_up",
}


def _tags(line: str) -> list:
    found = []
    for label, slug in TAG_MAP.items():
        if f"**{label}**" in line:
            found.append(slug)
    return found


def _cat_for_id(n: int) -> str:
    if n <= 20:
        return "compare_revenue"
    if n <= 40:
        return "category_breakdown"
    if n <= 60:
        return "follow_up"
    if n <= 75:
        return "charts"
    if n <= 95:
        return "store_overview"
    if n <= 110:
        return "rankings"
    if n <= 125:
        return "donations_door"
    if n <= 140:
        return "budget_periods"
    if n <= 148:
        return "trends"
    return "help_edge"


def load_v1() -> list:
    text = MD.read_text(encoding="utf-8")
    items = []
    for m in re.finditer(r"^(\d+)\.\s+(.+)$", text, re.M):
        n = int(m.group(1))
        raw = m.group(2).strip()
        if "B only" in raw:
            continue
        tags = _tags(raw)
        q = re.sub(r"\s*\*\*[^*]+\*\*", "", raw).strip()
        if "**A:**" in q:
            q = q.split("**A:**", 1)[-1].strip()
            tags.append("follow_up_a")
        items.append(
            {
                "id": n,
                "text": q,
                "category": _cat_for_id(n),
                "tags": tags,
                "source": "v1",
            }
        )
    # Pair B lines as separate follow-up prompts
    for m in re.finditer(
        r"^\d+\.\s+\*\*A:\*\*\s*(.+?)\s*\n\s*\*\*B:\*\*\s*(.+?)(?:\s+\*\*|$)",
        text,
        re.M | re.S,
    ):
        b = re.sub(r"\s*\*\*[^*]+\*\*", "", m.group(2)).strip()
        items.append(
            {
                "id": len(items) + 1,
                "text": b,
                "category": "follow_up",
                "tags": _tags(m.group(0)) + ["follow_up_b"],
                "source": "v1_pair_b",
            }
        )
    return items


def load_v2() -> list:
    """150 additional natural user questions (ids 151–300)."""
    raw = [
        # Key metrics & square footage (151–165)
        ("key_metrics", "What is the sales square footage for Marbach?"),
        ("key_metrics", "Show sales per square foot for Bandera year to date."),
        ("key_metrics", "Is Culebra leased or owned?"),
        ("key_metrics", "Compare Bandera and Culebra on sales per sq ft for 2026."),
        ("key_metrics", "Which store has the highest sales per square foot this year?"),
        ("key_metrics", "How big is the sales floor at DeZavala in square feet?"),
        ("key_metrics", "Key metrics snapshot for Potranco — sq ft, SPSF, lease status."),
        ("key_metrics", "Does Kerrville have more sales floor than New Braunfels?"),
        ("key_metrics", "Tier and square footage for Bitters."),
        ("key_metrics", "Annualized sales per sq ft for Commerce vs network average."),
        ("key_metrics", "List top 5 stores by sales per square foot YTD."),
        ("key_metrics", "Is Fredericksburg owned or leased and what is its sales sq ft?"),
        ("key_metrics", "Explain how sales per sq ft is calculated for this store."),
        ("key_metrics", "Which leased stores have the best sales per sq ft in April?"),
        ("key_metrics", "Square footage and tier for all stores I manage in division 1."),
        # Outlets & donation stations (166–180)
        ("outlet_adc", "How is SA Outlet performing vs regular retail stores in April?"),
        ("outlet_adc", "Compare Laredo Outlet to Laredo Central on revenue last month."),
        ("outlet_adc", "Donation station at Garden Ridge — how much did it collect in March?"),
        ("outlet_adc", "Rank donation stations by total donations in April."),
        ("outlet_adc", "Are donation stations busier on weekends? Check last 30 days."),
        ("outlet_adc", "Churchill Estates donation station vs Oak Park station — donations."),
        ("outlet_adc", "Do outlets have lower expense ratios than stores?"),
        ("outlet_adc", "Traffic at Leon Springs donation station this month."),
        ("outlet_adc", "Which ADC had the peak donation day in February?"),
        ("outlet_adc", "Consolidated view — retail vs donation station contribution."),
        ("outlet_adc", "Is Lakeside Plaza donation station growing YTD?"),
        ("outlet_adc", "Compare outlet door counts to outlet revenue for SA Outlet."),
        ("outlet_adc", "How many donation stations beat their March donations in April?"),
        ("outlet_adc", "SOHO donation station daily average donations this month."),
        ("outlet_adc", "Parkwood Place station — full month donation summary."),
        # Geography & clusters (181–195)
        ("geography", "How are San Antonio north-side stores doing in April?"),
        ("geography", "Compare all Kerrville-area performance to San Antonio average."),
        ("geography", "Laredo market total revenue and donations for Q1."),
        ("geography", "Which division had the best April revenue?"),
        ("geography", "Stores on the south side — rank by net income March."),
        ("geography", "New Braunfels and Seguin — sister cities comparison for April."),
        ("geography", "Loop 1604 corridor stores — revenue trend 6 months."),
        ("geography", "How does Cibolo compare to other suburban stores?"),
        ("geography", "I-35 corridor stores ranked by door count April."),
        ("geography", "Hill Country stores revenue share of the network."),
        ("geography", "Downtown San Antonio stores — Commerce and nearby comparison."),
        ("geography", "Which store is farthest below budget in my region?"),
        ("geography", "Spring Branch / Bulverde North cluster performance."),
        ("geography", "Potranco and Culebra west-side comparison with detail."),
        ("geography", "Market share style view — Bandera vs all SA stores April."),
        # Why / root cause / narrative (196–210)
        ("why_narrative", "Why did Culebra miss budget in April?"),
        ("why_narrative", "Why is Marbach door count down but revenue flat?"),
        ("why_narrative", "Explain why Bandera beat Culebra in April in plain English."),
        ("why_narrative", "What likely drove the spike at Bitters on April 12?"),
        ("why_narrative", "Root cause summary for DeZavala expense ratio increase."),
        ("why_narrative", "Tell me a story about Potranco’s March — good or bad and why."),
        ("why_narrative", "Why are donations soft at Fredericksburg this month?"),
        ("why_narrative", "Is underperformance at South Park a traffic issue or sales issue?"),
        ("why_narrative", "What changed week over week at Gateway in April?"),
        ("why_narrative", "Give me talking points for a leadership meeting on Culebra."),
        ("why_narrative", "Why did the network dip the second week of March?"),
        ("why_narrative", "Help me understand Evans April vs March in full sentences."),
        ("why_narrative", "What should the GM at Marbach focus on based on April data?"),
        ("why_narrative", "Diagnose Blanco North — revenue, traffic, donations together."),
        ("why_narrative", "Summarize risks for underperforming stores this quarter."),
        # Percent / growth (211–225)
        ("growth", "Percent change in revenue for Bandera March to April."),
        ("growth", "Which stores grew donations more than 10% April vs March?"),
        ("growth", "Culebra April revenue growth rate vs last year same month."),
        ("growth", "Show percent of budget attained for each store in March."),
        ("growth", "Fastest growing store by net income Q1 to Q2."),
        ("growth", "Did door count grow faster than revenue at Marbach?"),
        ("growth", "MoM percent change network-wide for core sales."),
        ("growth", "Bandera vs Culebra — percent difference in April revenue."),
        ("growth", "Donation growth trend for Potranco last 4 months."),
        ("growth", "Stores with negative revenue growth in April — list them."),
        ("growth", "How much did consolidated revenue grow YTD vs last year?"),
        ("growth", "Expense ratio change in basis points for DeZavala April vs March."),
        ("growth", "Traffic up or down percent for Bitters April vs March?"),
        ("growth", "Rank stores by percent over budget in April."),
        ("growth", "Revenue run rate for Culebra if April pace continues."),
        # Three+ store compares (226–240)
        ("multi_compare", "Compare Bandera, Culebra, and DeZavala for April revenue."),
        ("multi_compare", "Rank Bitters, Commerce, Fredericksburg, and Gateway for March door count."),
        ("multi_compare", "Who is winning among north stores: Blanco North, Evans, Gateway, Summit?"),
        ("multi_compare", "Table of April revenue for all Laredo locations."),
        ("multi_compare", "Top 3 and bottom 3 for sales per visit in March."),
        ("multi_compare", "Compare my top 5 stores on budget attainment in April."),
        ("multi_compare", "Show April core sales for every store on Bandera road corridor."),
        ("multi_compare", "Which of these is best: Marbach, South Park, WW White — April revenue?"),
        ("multi_compare", "Cluster compare — Bulverde, Bulverde North, Cibolo donations in April."),
        ("multi_compare", "Network leaderboard April — revenue, doors, donations columns."),
        ("multi_compare", "Compare Austin Hwy, Rittiman, and SA Outlet for Q1."),
        ("multi_compare", "Three-store chart: Potranco, Culebra, DeZavala monthly revenue."),
        ("multi_compare", "April category breakdown for Bandera, Culebra, and Marbach."),
        ("multi_compare", "Which store in the compare group has the worst expense ratio?"),
        ("multi_compare", "Side by side March vs April for Bandera and Culebra and Blanco."),
        # Week / day granularity (241–255)
        ("granularity", "Week-by-week revenue for Bandera in April."),
        ("granularity", "Which week of March was strongest for Culebra?"),
        ("granularity", "Daily door count pattern for Marbach in April — weekday vs weekend."),
        ("granularity", "Show me the worst sales day in April for DeZavala."),
        ("granularity", "How many days in April did Bitters beat $10k in core sales?"),
        ("granularity", "First half vs second half of April for Potranco revenue."),
        ("granularity", "Calendar heatmap style summary — busy days at Fredericksburg in March."),
        ("granularity", "Which day of week has the highest donations at Culebra?"),
        ("granularity", "Rolling 7-day average revenue for Gateway last 90 days."),
        ("granularity", "Compare week 1 and week 4 of April for Bandera and Culebra."),
        ("granularity", "Mid-month slump at Marbach — which days dragged April down?"),
        ("granularity", "Peak hour proxy — not available — but peak day for door count in April."),
        ("granularity", "List top 5 sales days in February for Potranco."),
        ("granularity", "Was Easter week stronger for donations network-wide?"),
        ("granularity", "Daily budget attainment for Culebra in April."),
        # Consolidated & executive (256–270)
        ("executive", "How is Goodwill SA performing overall this month?"),
        ("executive", "Executive summary of the Opportunity Center consolidated view."),
        ("executive", "Network KPI dashboard narrative for April."),
        ("executive", "Are we ahead or behind plan as an organization in April?"),
        ("executive", "Total donations and total revenue for the whole company YTD."),
        ("executive", "Which metric should leadership worry about most this month?"),
        ("executive", "Retail store count and average revenue per store in March."),
        ("executive", "Consolidated actual vs budget for core revenue April."),
        ("executive", "High-level trend — are we improving or declining over 12 months?"),
        ("executive", "Biggest win and biggest miss for the network in April."),
        ("executive", "Compare SA market to Kerrville market contribution in Q1."),
        ("executive", "Donation dollars per retail store visit network average."),
        ("executive", "Expense ratio at consolidated level vs last year."),
        ("executive", "Strategic view — stores to invest in based on SPSF and growth."),
        ("executive", "One-page brief: April performance for all retail stores."),
        # Casual / typos / natural (271–285)
        ("casual", "hows bandera doing"),
        ("casual", "culebra vs bandera april sales pls"),
        ("casual", "need chart bandera culebra"),
        ("casual", "what categories bandera april"),
        ("casual", "door count marbach last month?"),
        ("casual", "top store revenue march"),
        ("casual", "is potranco over budget"),
        ("casual", "donations down at bitters?"),
        ("casual", "compare them on traffic"),  # follow-up style
        ("casual", "same month last year?"),
        ("casual", "more detail pls"),
        ("casual", "break it down by category"),
        ("casual", "whos winning bandera or culebra"),
        ("casual", "show trend 12 mo culebra"),
        ("casual", "what can u tell me about store data"),
        # Extra follow-ups & charts (286–300)
        ("follow_up", "Now show categories for that comparison."),
        ("follow_up", "Add expense ratio to those two stores."),
        ("follow_up", "Same stores, March instead."),
        ("follow_up", "Chart it please."),
        ("follow_up", "I need more than one sentence."),
        ("follow_up", "Break down donations too."),
        ("follow_up", "What about door count?"),
        ("follow_up", "Explain for my VP."),
        ("follow_up", "Which categories explain the gap?"),
        ("follow_up", "Show the monthly trend for both."),
        ("follow_up", "Compare on net income instead."),
        ("follow_up", "Was either store over budget?"),
        ("follow_up", "Give me revenue per visitor for both."),
        ("follow_up", "Now do Kerrville instead of Bandera."),
        ("follow_up", "Keep Culebra — swap the other store to DeZavala."),
        ("compare_revenue", "Draw a comparison graph for sales in Bandera and Culebra for April."),
        ("category_breakdown", "Show revenue types for Bandera and Culebra in April side by side."),
        ("charts", "Visualize category differences between Bandera and Culebra for April."),
        ("store_overview", "Full performance narrative for the store I have selected on the map."),
        ("rankings", "Which store had the best sales day network-wide in April?"),
        ("donations_door", "Correlation between donations and door count at Marbach for 60 days."),
        ("budget_periods", "How did April actual compare to budget for Bandera and Culebra?"),
        ("trends", "Show revenue and donations trend together for Culebra for 1 year."),
        ("help_edge", "What types of questions can you answer about categories and comparisons?"),
        ("why_narrative", "Give a detailed comparison overview of Bandera vs Culebra for April."),
    ]
    out = []
    for i, (cat, q) in enumerate(raw, start=151):
        tags = ["follow_up"] if cat == "follow_up" else []
        if cat == "category_breakdown" or "categor" in q.lower():
            tags.append("category")
        if "chart" in q.lower() or "graph" in q.lower():
            tags.append("chart")
        if any(w in q.lower() for w in ("overview", "detail", "explain", "summary", "brief", "story")):
            tags.append("detail")
        out.append({"id": i, "text": q, "category": cat, "tags": tags, "source": "v2"})
    return out


def main():
    v1 = load_v1()
    v2 = load_v2()
    # Re-number v1 sequentially 1..150 if needed
    bank = []
    seen = set()
    for item in sorted(v1, key=lambda x: x["id"]):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        bank.append(item)
    # Pad v1 to 150 if pairs added extra ids
    v1_ids = {x["id"] for x in bank if x["source"] == "v1"}
    for item in bank:
        if item["source"] == "v1_pair_b":
            nid = max(v1_ids or [0]) + 1
            while nid in seen:
                nid += 1
            item["id"] = nid
            seen.add(nid)
    bank = sorted(bank, key=lambda x: x["id"])[:150]
    for item in v2:
        bank.append(item)
    bank = bank[:300]
    # Ensure ids 1..300
    for i, item in enumerate(bank, start=1):
        item["id"] = i
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "total": len(bank),
        "questions": bank,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(bank)} questions to {OUT}")


if __name__ == "__main__":
    main()
