"""JSON Schema tool definitions for the chat assistant.

Schemas only — each ToolSpec in registry.py binds its schema constant
directly, so a schema with no ToolSpec is dead code (vulture catches it) and
a ToolSpec with no schema cannot be constructed.
Descriptions are 3-4 sentences minimum per Anthropic's guidance — the single
most important factor in tool selection quality.

Opus 4.8 under-reaches for tools unless told when to use them, so every
description leads with an explicit trigger ("Call this when...") — the
opposite of the Sonnet 4.6 tuning this file originally carried.
"""

GET_SETTLEMENT_BALANCE_SCHEMA: dict[str, object] = {
    "name": "get_settlement_balance",
    "description": (
        "Call this whenever the user asks who owes whom, what's "
        "outstanding, whether they're settled up, or anything about the "
        "settlement ledger — always look it up rather than answering from "
        "conversation memory, since balances change as transactions are "
        "edited. "
        "Omit year and month to get the total outstanding balance across "
        "all months (outstanding: who owes whom in total, plus the span "
        "of months it covers) — this answers 'what do we owe each other?'. "
        "Provide year and month to inspect one month: its gross amount "
        "(who owed whom before payments), the month's ledger row "
        "(applied, remaining, status: settled / partially_settled / "
        "carried_forward), the remaining balance with its direction "
        "(net_from/net_to), upload status for each person, and whether "
        "the month is finalized."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "year": {
                "type": "integer",
                "description": (
                    "The year (e.g. 2026). Omit together with month "
                    "for the total outstanding across all months."
                ),
            },
            "month": {
                "type": "integer",
                "description": "The month (1-12). Omit together with year.",
            },
        },
        "required": [],
    },
}

GET_BUDGET_OVERVIEW_SCHEMA: dict[str, object] = {
    "name": "get_budget_overview",
    "description": (
        "Call this when the user asks whether they're on budget, over "
        "budget, how much is left in a category, or anything comparing "
        "spending against a target. "
        "Gets budget progress for all category groups in a given month. "
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
}

SEARCH_TRANSACTIONS_SCHEMA: dict[str, object] = {
    "name": "search_transactions",
    "description": (
        "Call this when the user mentions a specific merchant, purchase, "
        "or transaction — and ALWAYS call it before proposing any "
        "transaction mutation, because mutation tools require real "
        "transaction IDs from these results. "
        "Searches transactions for a given month with optional filters. "
        "Supports merchant name substring matching, category group "
        "filtering, and tag filtering. The scope parameter controls "
        "which transactions are considered: 'all' (default) searches "
        "every transaction regardless of household or personal status "
        "— use this when finding transactions to tag, re-categorize, or "
        "re-split, since those actions aren't limited to household rows. "
        "'household' searches only household-flagged transactions. "
        "'personal' searches the current user's personal spending "
        "(their own non-household transactions, plus their share of "
        "transactions where a partner fronted money on their behalf). "
        "Returns up to 20 matching transactions with date, merchant, "
        "category, amount, payer, split ratio, and household flag, plus "
        "the total count of matches."
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
            "scope": {
                "type": "string",
                "enum": ["all", "household", "personal"],
                "description": (
                    "Which transactions to search. Default 'all'. Use "
                    "'all' when the goal is finding transactions to "
                    "mutate (tag, re-categorize, re-split) so household "
                    "status never hides a match."
                ),
            },
        },
        "required": ["year", "month"],
    },
    "input_examples": [
        {"year": 2026, "month": 3, "merchant": "Whole Foods"},
        {"year": 2026, "month": 3, "category_group": "Food & Dining"},
        {"year": 2026, "month": 3, "tag": "discuss"},
        {"year": 2026, "month": 3, "merchant": "Uber Eats", "scope": "all"},
    ],
}

GET_SPENDING_BY_GROUP_SCHEMA: dict[str, object] = {
    "name": "get_spending_by_group",
    "description": (
        "Call this when the user asks where the money went or how much "
        "they spent in a month and no budget comparison is needed. "
        "Gets total household spending broken down by category group for "
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
}

GET_SPENDING_TRENDS_SCHEMA: dict[str, object] = {
    "name": "get_spending_trends",
    "description": (
        "Call this when the user asks about trends, changes over time, "
        "year-over-year comparisons, or 'how's this year going' — any "
        "question spanning more than one or two months. "
        "Gets monthly spending trends per category group across a full "
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
}

GET_DASHBOARD_STATUS_SCHEMA: dict[str, object] = {
    "name": "get_dashboard_status",
    "description": (
        "Call this when the user asks about readiness or workflow state — "
        "'did we both upload?', 'is March locked?', 'are we ready to "
        "settle?' — or before advising on the monthly ritual. "
        "Checks operational status for a given month: whether each person "
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
}

# --- Mutation tools (two-phase confirmation) ---

UPDATE_BUDGET_SCHEMA: dict[str, object] = {
    "name": "update_budget",
    "description": (
        "Call this when the user asks to set, change, or create a budget "
        "for a category group — don't just describe the change, propose "
        "it. Creates the budget when none exists, updates it otherwise. "
        "Returns a pending confirmation — the change is NOT applied until "
        "the user confirms via the confirmation card. The group_name must "
        "match an existing category group exactly. Scope defaults to "
        "'household'; use 'personal' for the current user's personal budget."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "group_name": {
                "type": "string",
                "description": "Category group name (exact match, e.g. 'Food & Dining').",
            },
            "amount": {
                "type": "number",
                "description": "Monthly budget amount in dollars (e.g. 700).",
            },
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
        "required": ["group_name", "amount", "year", "month"],
    },
}

UPDATE_TRANSACTION_SPLIT_SCHEMA: dict[str, object] = {
    "name": "update_transaction_split",
    "description": (
        "Call this when the user wants to change how a single transaction "
        "is split between them (e.g. 'make that 70/30', 'Bob should cover "
        "that one') — don't just explain, propose the change. "
        "The transaction_id is a UUID returned by "
        "search_transactions — never guess or fabricate an ID. Always call "
        "search_transactions first to find the matching transaction, then "
        "use its id field. Returns a pending confirmation card."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "transaction_id": {
                "type": "string",
                "description": "Transaction UUID from search_transactions results.",
            },
            "payer_percentage": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "The payer's share (0-100). 50 = 50/50, 0 = spotted.",
            },
        },
        "required": ["transaction_id", "payer_percentage"],
    },
}

BULK_UPDATE_TRANSACTIONS_SCHEMA: dict[str, object] = {
    "name": "bulk_update_transactions",
    "description": (
        "Call this when the user wants to change several transactions at "
        "once — tagging, re-categorizing, marking household, excluding, "
        "or re-splitting a set (e.g. 'tag all the Uber Eats runs as "
        "household'). Maximum 100 "
        "transaction IDs per call. All transaction_ids must come from "
        "search_transactions results — never fabricate IDs. Changes can "
        "include the household flag, split percentage, exclusion status, "
        "category, or tag modifications. Returns a pending confirmation "
        "card listing the affected transactions and proposed changes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "transaction_ids": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 100,
                "description": "Transaction UUIDs from search_transactions.",
            },
            "changes": {
                "type": "object",
                "description": "Fields to update on all transactions.",
                "properties": {
                    "household": {
                        "type": "boolean",
                        "description": "Set the household flag.",
                    },
                    "payer_percentage": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Set the payer's share (0-100).",
                    },
                    "is_excluded": {
                        "type": "boolean",
                        "description": "Exclude from settlement and budget.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Set the category name.",
                    },
                    "tags": {
                        "type": "object",
                        "description": "Tag modification.",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["add", "remove"],
                            },
                            "values": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["action", "values"],
                    },
                },
            },
        },
        "required": ["transaction_ids", "changes"],
    },
}
