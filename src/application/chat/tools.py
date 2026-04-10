"""JSON Schema tool definitions for the chat assistant.

Each tool wraps an existing read-only use case. Descriptions are 3-4 sentences
minimum per Anthropic's guidance — the single most important factor in tool
selection quality.

Sonnet 4.6 is more proactive about tool selection than earlier models, so
descriptions focus on what the tool does and returns rather than prescriptive
"use this when..." routing (which causes overtriggering).
"""

from anthropic.types import ToolParam

TOOLS: list[ToolParam] = [
    {
        "name": "get_settlement_balance",
        "description": (
            "Look up settlement status for a given month. Returns the gross "
            "settlement amount (who owes whom before any payments), remaining "
            "balance after recorded settlements, upload status for each person, "
            "and whether the month is finalized. Also returns warning flags if "
            "uploads are missing or the balance is unsettled."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "The year (e.g. 2026).",
                },
                "month": {
                    "type": "integer",
                    "description": "The month (1-12).",
                },
            },
            "required": ["year", "month"],
        },
    },
    {
        "name": "get_budget_overview",
        "description": (
            "Get budget progress for all category groups in a given month. "
            "Returns each group's monthly budget amount, actual spending, "
            "year-to-date totals, and health status (on_track, near_limit, "
            "or over_budget). Groups with no budget set show null for budget "
            "and health fields. Supports both household and personal scope."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "The year (e.g. 2026).",
                },
                "month": {
                    "type": "integer",
                    "description": "The month (1-12).",
                },
                "scope": {
                    "type": "string",
                    "enum": ["household", "personal"],
                    "description": "Budget scope. Default 'household'.",
                },
            },
            "required": ["year", "month"],
        },
    },
    {
        "name": "search_transactions",
        "description": (
            "Search household transactions for a given month with optional "
            "filters. Supports merchant name substring matching, category "
            "group filtering, and tag filtering. Returns up to 20 matching "
            "transactions with date, merchant, category, amount, payer, split "
            "ratio, and household flag, plus the total count of matches."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "The year (e.g. 2026).",
                },
                "month": {
                    "type": "integer",
                    "description": "The month (1-12).",
                },
                "merchant": {
                    "type": "string",
                    "description": "Substring to match against merchant names (case-insensitive).",
                },
                "category_group": {
                    "type": "string",
                    "description": "Category group name to filter by (exact match).",
                },
                "tag": {
                    "type": "string",
                    "description": "Tag to filter by (e.g. 'discuss', 'shared').",
                },
            },
            "required": ["year", "month"],
        },
        "input_examples": [
            {"year": 2026, "month": 3, "merchant": "Whole Foods"},
            {"year": 2026, "month": 3, "category_group": "Food & Dining"},
            {"year": 2026, "month": 3, "tag": "discuss"},
        ],
    },
    {
        "name": "get_spending_by_group",
        "description": (
            "Get total household spending broken down by category group for "
            "a given month. Returns each group name and its spending total. "
            "Simpler than get_budget_overview — only spending amounts, no "
            "budget comparisons or health indicators."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "The year (e.g. 2026).",
                },
                "month": {
                    "type": "integer",
                    "description": "The month (1-12).",
                },
            },
            "required": ["year", "month"],
        },
    },
    {
        "name": "get_spending_trends",
        "description": (
            "Get monthly spending trends per category group across a full "
            "year. Returns each group's spending amount for every month that "
            "has transaction data. Optionally includes a comparison year for "
            "year-over-year analysis. Does not include budget amounts — use "
            "get_budget_overview for budget comparisons."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "The year to analyze (e.g. 2026).",
                },
                "comparison_year": {
                    "type": "integer",
                    "description": "Optional year to compare against (e.g. 2025).",
                },
            },
            "required": ["year"],
        },
    },
    {
        "name": "get_dashboard_status",
        "description": (
            "Check operational status for a given month: whether each person "
            "has uploaded their Monarch CSV, the total transaction count, and "
            "whether the month is finalized (locked against further changes). "
            "Useful for checking readiness before settling up or reviewing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "The year (e.g. 2026).",
                },
                "month": {
                    "type": "integer",
                    "description": "The month (1-12).",
                },
            },
            "required": ["year", "month"],
        },
        "cache_control": {"type": "ephemeral"},
    },
]
