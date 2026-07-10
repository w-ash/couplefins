"""JSON Schema tool definitions for the chat assistant.

Schemas only — each ToolSpec in registry.py binds its schema constant
directly, so a schema with no ToolSpec is dead code (vulture catches it) and
a ToolSpec with no schema cannot be constructed.
Descriptions are 3-4 sentences minimum per Anthropic's guidance — the single
most important factor in tool selection quality.

Opus 4.8 under-reaches for tools unless told when to use them, so every
description leads with an explicit trigger ("Call this when...") — the
opposite of the Sonnet 4.6 tuning this file originally carried.

Every schema sets strict: true (guaranteed schema-conformant calls), which
requires additionalProperties: false and rejects numeric/array constraints
(minimum, maximum, maxItems — the API 400s on them). State ranges in the
property description and enforce them in the handler instead.
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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

GET_TAGS_SCHEMA: dict[str, object] = {
    "name": "get_tags",
    "description": (
        "Call this when the user asks what tags exist, how things are "
        "tagged, or before filtering by a tag whose exact spelling you "
        "don't know. "
        "Returns the distinct tags across all imported transactions. "
        "Useful before search_transactions with a tag filter, or before "
        "proposing tag changes with bulk_update_transactions."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "required": [],
    },
}

GET_TRANSACTION_HISTORY_SCHEMA: dict[str, object] = {
    "name": "get_transaction_history",
    "description": (
        "Call this when the user asks who changed a transaction, what its "
        "original values were, or when it was imported. "
        "Returns the edit timeline for one transaction (field, old value, "
        "new value, when, by whom) plus its import provenance (who uploaded "
        "it and when). The transaction_id must come from search_transactions "
        "results — never guess an ID."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "transaction_id": {
                "type": "string",
                "description": "Transaction UUID from search_transactions results.",
            },
        },
        "required": ["transaction_id"],
    },
}

GET_BUDGETS_SCHEMA: dict[str, object] = {
    "name": "get_budgets",
    "description": (
        "Call this when the user asks which budgets are configured, what a "
        "budget amount is set to, or which months have budgets — questions "
        "about the configured amounts themselves, with no spending "
        "comparison. For 'are we on/over budget' questions use "
        "get_budget_overview instead. "
        "Returns the raw budget rows visible to the current user: category "
        "group, monthly amount, month, and scope (household budgets are "
        "shared; personal budgets are the current user's own)."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "year": {
                "type": "integer",
                "description": "The year (e.g. 2026).",
            },
            "month": {
                "type": "integer",
                "description": "The month (1-12). Omit for all months of the year.",
            },
            "scope": {
                "type": "string",
                "enum": ["household", "personal", "all"],
                "description": (
                    "Which budgets to list. Default 'all' (both household "
                    "and the current user's personal budgets)."
                ),
            },
        },
        "required": ["year"],
    },
}

GET_CATEGORY_SETUP_SCHEMA: dict[str, object] = {
    "name": "get_category_setup",
    "description": (
        "Call this when the user asks how their categories are organized, "
        "which group a category belongs to, which categories count personal "
        "spending toward the budget, or whether anything is unmapped. "
        "Returns every category group with its member categories, the "
        "categories flagged include_personal (their group's budget also "
        "counts personal transactions), and the list of categories not yet "
        "mapped to any group."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "required": [],
    },
}

GET_UPLOAD_HISTORY_SCHEMA: dict[str, object] = {
    "name": "get_upload_history",
    "description": (
        "Call this when the user asks what has been uploaded, when someone "
        "last imported their CSV, or how many transactions an upload "
        "brought in. "
        "Returns recent Monarch CSV uploads, newest first: who uploaded, "
        "filename, when, the date range covered, and transaction counts "
        "(total and household). Default 12 entries."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum entries to return (1-20). Default 12.",
            },
        },
        "required": [],
    },
}

GET_RECONCILIATION_REPORT_SCHEMA: dict[str, object] = {
    "name": "get_reconciliation_report",
    "description": (
        "Call this when the user wants the month's full reconciliation "
        "picture — total household spending, refunds, each person's paid "
        "vs. fair share, and the gross settlement position — the numbers "
        "the Transactions page summary shows. "
        "Use response_format 'concise' (default) for totals and per-person "
        "nets; 'detailed' adds the per-category-group breakdown and the "
        "largest transactions. For the running who-owes-whom balance use "
        "get_settlement_balance instead — this report is the month's gross "
        "position before payments."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "year": {
                "type": "integer",
                "description": "The year (e.g. 2026).",
            },
            "month": {
                "type": "integer",
                "description": "The month (1-12).",
            },
            "response_format": {
                "type": "string",
                "enum": ["concise", "detailed"],
                "description": (
                    "'concise' (default): totals + per-person nets + "
                    "settlement. 'detailed': adds per-group breakdown and "
                    "the largest transactions (max 20 rows)."
                ),
            },
        },
        "required": ["year", "month"],
    },
    "input_examples": [
        {"year": 2026, "month": 6},
        {"year": 2026, "month": 6, "response_format": "detailed"},
    ],
}

GET_SETTLEMENT_ACTIVITY_SCHEMA: dict[str, object] = {
    "name": "get_settlement_activity",
    "description": (
        "Call this when the user asks about recorded settlement payments "
        "(who paid, when, how much, what they covered), about linking a "
        "bank transfer to a settlement, or before proposing any settlement "
        "mutation — it surfaces the settlement and transaction IDs those "
        "mutations need. "
        "Returns for the given month context: recorded payments with their "
        "FIFO coverage and linked transactions, transactions that look like "
        "the outstanding settlement transfer (candidates, scored), and the "
        "configured settlement merchant patterns."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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

GET_DASHBOARD_SUMMARY_SCHEMA: dict[str, object] = {
    "name": "get_dashboard_summary",
    "description": (
        "Call this when the user asks how the year is going, wants the "
        "overview the Dashboard page shows, or asks about a past month's "
        "totals — year-to-date spending, total settled this year, and the "
        "month-by-month history with each month's settlement status. "
        "Scope 'household' (default) covers shared spending; 'personal' "
        "adds the current user's own spending and their household share. "
        "For single-month budget health use get_budget_overview; for "
        "upload/finalization readiness use get_dashboard_status."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "year": {
                "type": "integer",
                "description": "The year (e.g. 2026).",
            },
            "month": {
                "type": "integer",
                "description": (
                    "The month (1-12) for the current-month figures. "
                    "Defaults to the latest month with data."
                ),
            },
            "scope": {
                "type": "string",
                "enum": ["household", "personal"],
                "description": "Dashboard scope. Default 'household'.",
            },
        },
        "required": ["year"],
    },
}

GET_ADJUSTMENTS_PREVIEW_SCHEMA: dict[str, object] = {
    "name": "get_adjustments_preview",
    "description": (
        "Call this when the user asks what adjustment entries a month would "
        "produce for their Monarch import — the correcting entries that "
        "make their personal spending totals accurate after splits. "
        "Returns the current user's adjustment rows for the month (date, "
        "merchant, category, amount, account) as the CSV export would "
        "contain them. Requires the user's adjustment account to be "
        "configured in their profile; the actual file download is only "
        "available in the app."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "transaction_id": {
                "type": "string",
                "description": "Transaction UUID from search_transactions results.",
            },
            "payer_percentage": {
                "type": "integer",
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
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "transaction_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Transaction UUIDs from search_transactions (max 100).",
            },
            "changes": {
                "type": "object",
                "additionalProperties": False,
                "description": "Fields to update on all transactions.",
                "properties": {
                    "household": {
                        "type": "boolean",
                        "description": "Set the household flag.",
                    },
                    "payer_percentage": {
                        "type": "integer",
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
                        "additionalProperties": False,
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
