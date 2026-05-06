"""Catalogs for planner, router, and response typing (GWSA AI model)."""

INTENT_ACTIONS = frozenset({
    "none",
    "location_summary",
    "compare_locations",
    "rank_locations",
    "rank_time_periods",
    "trend_summary",
    "metric_breakdown",
    "multi_metric_summary",
    "compare_periods",
    "correlation_check",
    "derived_metric",
    "data_catalog",
    "map_context_summary",
    "peak_store_daily_revenue",
    "unsupported",
})

INTENT_METRICS = frozenset({
    "revenue", "door_count", "net_income", "operating_expenses",
    "personnel_expenses", "expense_ratio",
})

RANK_HINTS = ("highest", "best", "top", "most", "lowest", "least")
COMPARE_HINTS = ("compare", "vs", "versus", "against")
SUMMARY_HINTS = ("summary", "how is", "how's", "performance", "doing")

MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
