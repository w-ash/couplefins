"""JSON Schema tool definitions for the chat assistant.

Schemas only — each ToolSpec in registry.py binds its schema constant
directly, so a schema with no ToolSpec is dead code (vulture catches it) and
a ToolSpec with no schema cannot be constructed.
Descriptions are 3-4 sentences minimum per Anthropic's guidance — the single
most important factor in tool selection quality.

Opus 4.8 under-reaches for tools unless told when to use them, so every
description leads with an explicit trigger ("Call this when...") — the
opposite of the Sonnet 4.6 tuning this file originally carried.

No schema sets strict: true. It was tried in v1.8.1/v1.8.2 and abandoned
after three live-verified API limits at this registry size (31 tools): a cap
of 20 strict tools per request, a compiled-grammar size cap ("The compiled
grammar is too large") even at 16, and strict's rejection of numeric/array
constraints (minimum, maximum, maxItems). Handlers validate every input at
the boundary instead — state ranges in the property description and enforce
them in the handler. All schemas keep additionalProperties: false, and
strict remains incompatible with v1.8.3's allowed_callers anyway.
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
        "Call this when the user wants to change how transactions are "
        "split between them (e.g. 'make that 70/30', 'Bob should cover "
        "that one', 'split all three rent charges 60/40') — don't just "
        "explain, propose the change. For one transaction pass "
        "transaction_id + payer_percentage; for several pass the splits "
        "array (each entry with its own percentage). All IDs are UUIDs "
        "returned by search_transactions — never guess or fabricate an "
        "ID. Returns a pending confirmation card."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "transaction_id": {
                "type": "string",
                "description": (
                    "Single-transaction form: transaction UUID from "
                    "search_transactions results."
                ),
            },
            "payer_percentage": {
                "type": "integer",
                "description": (
                    "Single-transaction form: the payer's share (0-100). "
                    "50 = 50/50, 0 = spotted."
                ),
            },
            "splits": {
                "type": "array",
                "description": (
                    "Batch form: one entry per transaction (max 100). "
                    "Overrides the single-transaction fields."
                ),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "transaction_id": {
                            "type": "string",
                            "description": "Transaction UUID.",
                        },
                        "payer_percentage": {
                            "type": "integer",
                            "description": "The payer's share (0-100).",
                        },
                    },
                    "required": ["transaction_id", "payer_percentage"],
                },
            },
        },
        "required": [],
    },
    "input_examples": [
        {"transaction_id": "1c9e...", "payer_percentage": 70},
        {
            "splits": [
                {"transaction_id": "1c9e...", "payer_percentage": 60},
                {"transaction_id": "2d8f...", "payer_percentage": 60},
            ]
        },
    ],
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

DELETE_BUDGET_SCHEMA: dict[str, object] = {
    "name": "delete_budget",
    "description": (
        "Call this when the user asks to remove or clear a budget for a "
        "category group in a given month. Proposes the deletion — nothing "
        "is applied until the user confirms via the confirmation card, "
        "which shows the current amount being deleted. The group_name must "
        "match an existing category group with a budget configured for "
        "that month and scope."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "group_name": {
                "type": "string",
                "description": "Category group name (exact match).",
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
        "required": ["group_name", "year", "month"],
    },
}

COPY_BUDGETS_SCHEMA: dict[str, object] = {
    "name": "copy_budgets",
    "description": (
        "Call this when the user wants to reuse a month's budgets for "
        "another month ('same budgets as June', 'copy May's budgets to "
        "July'). Proposes copying every budget (household plus the current "
        "user's personal) from the source month to the target month — "
        "groups that already have a target budget are skipped, never "
        "overwritten. Nothing is applied until the user confirms."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "from_year": {
                "type": "integer",
                "description": "Source year (e.g. 2026).",
            },
            "from_month": {
                "type": "integer",
                "description": "Source month (1-12).",
            },
            "to_year": {
                "type": "integer",
                "description": "Target year (e.g. 2026).",
            },
            "to_month": {
                "type": "integer",
                "description": "Target month (1-12).",
            },
        },
        "required": ["from_year", "from_month", "to_year", "to_month"],
    },
}

MANAGE_CATEGORY_GROUP_SCHEMA: dict[str, object] = {
    "name": "manage_category_group",
    "description": (
        "Call this when the user wants to create, rename, or delete a "
        "category group (the budget-level grouping, e.g. 'Food & Dining') "
        "— not individual categories, which map_categories handles. "
        "Proposes the change; nothing is applied until the user confirms. "
        "Deleting a group requires deciding where its categories go: pass "
        "move_categories_to with another group's name, or omit it to leave "
        "them unmapped. The group's budgets are deleted with it."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "rename", "delete"],
                "description": "What to do with the group.",
            },
            "name": {
                "type": "string",
                "description": (
                    "The group name. For create: the new group's name. For "
                    "rename/delete: the existing group (exact match)."
                ),
            },
            "new_name": {
                "type": "string",
                "description": "Rename only: the new name for the group.",
            },
            "move_categories_to": {
                "type": "string",
                "description": (
                    "Delete only: group name to move the deleted group's "
                    "categories to. Omit to leave them unmapped."
                ),
            },
        },
        "required": ["action", "name"],
    },
    "input_examples": [
        {"action": "create", "name": "Pets"},
        {"action": "rename", "name": "Playa", "new_name": "Burning Man"},
        {"action": "delete", "name": "Festivals", "move_categories_to": "Lifestyle"},
    ],
}

MAP_CATEGORIES_SCHEMA: dict[str, object] = {
    "name": "map_categories",
    "description": (
        "Call this when the user wants to assign categories to category "
        "groups — mapping unmapped categories after an upload, or moving a "
        "category to a different group. Proposes the mapping; nothing is "
        "applied until the user confirms. Each group_name must match an "
        "existing category group exactly (see get_category_setup); "
        "categories that don't exist yet are created with the mapping."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "mappings": {
                "type": "array",
                "description": "Category → group assignments.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Category name.",
                        },
                        "group_name": {
                            "type": "string",
                            "description": "Target category group (exact match).",
                        },
                    },
                    "required": ["category", "group_name"],
                },
            },
        },
        "required": ["mappings"],
    },
}

SET_CATEGORY_PERSONAL_SCHEMA: dict[str, object] = {
    "name": "set_category_personal",
    "description": (
        "Call this when the user wants a category's budget to also count "
        "personal (non-household) spending — or to stop counting it. "
        "Proposes toggling the category's include_personal flag; nothing "
        "is applied until the user confirms. The category must already "
        "exist (see get_category_setup)."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "category": {
                "type": "string",
                "description": "Category name (exact match).",
            },
            "include_personal": {
                "type": "boolean",
                "description": (
                    "true: personal transactions in this category count "
                    "toward its group's budget. false: household only."
                ),
            },
        },
        "required": ["category", "include_personal"],
    },
}

FINALIZE_PERIOD_SCHEMA: dict[str, object] = {
    "name": "finalize_period",
    "description": (
        "Call this when the user wants to finalize, close, or lock a month "
        "after settling up. Proposes the finalization; nothing is applied "
        "until the user confirms. The confirmation card surfaces advisory "
        "warnings (missing uploads, outstanding balance, unmapped "
        "categories) — they don't block, matching the app. Finalizing "
        "locks the month's transactions against uploads and edits; "
        "payments against the ledger stay possible."
    ),
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
            "notes": {
                "type": "string",
                "description": "Optional closing notes recorded on the period.",
            },
        },
        "required": ["year", "month"],
    },
}

UNFINALIZE_PERIOD_SCHEMA: dict[str, object] = {
    "name": "unfinalize_period",
    "description": (
        "Call this when the user wants to unlock, reopen, or unfinalize a "
        "previously finalized month so transactions can be edited again. "
        "Proposes the unlock; nothing is applied until the user confirms. "
        "The month must currently be finalized."
    ),
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

RECORD_SETTLEMENT_SCHEMA: dict[str, object] = {
    "name": "record_settlement",
    "description": (
        "Call this when the user says a settlement payment happened — 'I "
        "paid Bob back', 'record the $500 Venmo'. Proposes recording the "
        "payment against the running ledger; nothing is applied until the "
        "user confirms. Payments apply to the oldest open months first "
        "(FIFO) — year/month is only a display annotation ('recorded "
        "against April'), never math. Optionally link the matching bank "
        "transaction(s) using IDs from get_settlement_activity's "
        "candidates, which excludes them from settlement math."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "from_person": {
                "type": "string",
                "description": "Name of the person who paid.",
            },
            "to_person": {
                "type": "string",
                "description": "Name of the person who was paid.",
            },
            "amount": {
                "type": "number",
                "description": "Payment amount in dollars (positive).",
            },
            "method": {
                "type": "string",
                "description": "How it was paid (e.g. 'Venmo', 'Zelle', 'cash').",
            },
            "notes": {
                "type": "string",
                "description": "Optional note stored on the settlement.",
            },
            "year": {
                "type": "integer",
                "description": (
                    "Optional 'recorded against' annotation year — display "
                    "only, set together with month."
                ),
            },
            "month": {
                "type": "integer",
                "description": (
                    "Optional 'recorded against' annotation month (1-12) — "
                    "display only, set together with year."
                ),
            },
            "linked_transaction_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional transaction UUIDs to link (from "
                    "get_settlement_activity candidates)."
                ),
            },
        },
        "required": ["from_person", "to_person", "amount"],
    },
}

WAIVE_SETTLEMENT_SCHEMA: dict[str, object] = {
    "name": "waive_settlement",
    "description": (
        "Call this when the user wants to forgive or write off the "
        "outstanding balance without money changing hands — 'let's call it "
        "even', 'waive what I owe'. Proposes waiving the TOTAL outstanding "
        "balance across all months (the running ledger, not one month); "
        "nothing is applied until the user confirms. Fails when nothing is "
        "outstanding."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "notes": {
                "type": "string",
                "description": "Optional note recording why the balance was waived.",
            },
        },
        "required": [],
    },
}

DELETE_SETTLEMENT_SCHEMA: dict[str, object] = {
    "name": "delete_settlement",
    "description": (
        "Call this when the user wants to remove a recorded settlement "
        "payment — a duplicate, a wrong amount, a mistake. Proposes the "
        "deletion; nothing is applied until the user confirms. The "
        "settlement_id must come from get_settlement_activity. Deleting "
        "also unlinks any linked transactions (their months must not be "
        "finalized), and the ledger recomputes."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "settlement_id": {
                "type": "string",
                "description": "Settlement UUID from get_settlement_activity.",
            },
        },
        "required": ["settlement_id"],
    },
}

LINK_SETTLEMENT_TRANSACTION_SCHEMA: dict[str, object] = {
    "name": "link_settlement_transaction",
    "description": (
        "Call this when the user wants to mark a bank transaction as a "
        "settlement transfer — usually one of get_settlement_activity's "
        "candidates ('yes, that Venmo is the payment'). Proposes marking "
        "the transaction is_settlement (excluding it from spending and "
        "settlement math), optionally linking it to a recorded settlement; "
        "nothing is applied until the user confirms. IDs come from "
        "get_settlement_activity or search_transactions."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "transaction_id": {
                "type": "string",
                "description": "Transaction UUID to mark as a settlement transfer.",
            },
            "settlement_id": {
                "type": "string",
                "description": ("Optional settlement UUID to link the transaction to."),
            },
        },
        "required": ["transaction_id"],
    },
}

UNLINK_SETTLEMENT_TRANSACTION_SCHEMA: dict[str, object] = {
    "name": "unlink_settlement_transaction",
    "description": (
        "Call this when the user says a transaction was wrongly linked to "
        "a settlement ('that Venmo wasn't the payment'). Proposes removing "
        "the link between the settlement and the transaction — when it was "
        "the transaction's only link, its is_settlement flag clears and it "
        "re-enters settlement math. Nothing is applied until the user "
        "confirms. Both IDs come from get_settlement_activity."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "settlement_id": {
                "type": "string",
                "description": "Settlement UUID the transaction is linked to.",
            },
            "transaction_id": {
                "type": "string",
                "description": "Transaction UUID to unlink.",
            },
        },
        "required": ["settlement_id", "transaction_id"],
    },
}

MANAGE_SETTLEMENT_MERCHANT_SCHEMA: dict[str, object] = {
    "name": "manage_settlement_merchant",
    "description": (
        "Call this when the user wants the app to recognize (or stop "
        "recognizing) a payment service when suggesting settlement "
        "candidates — 'also match Wise transfers', 'remove the PayPal "
        "pattern'. Proposes adding or removing a settlement merchant "
        "pattern; nothing is applied until the user confirms. Existing "
        "patterns are listed by get_settlement_activity."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "remove"],
                "description": "Add a new pattern or remove an existing one.",
            },
            "name": {
                "type": "string",
                "description": (
                    "Merchant display name (e.g. 'Wise'). For remove: must "
                    "match an existing merchant's name."
                ),
            },
            "pattern": {
                "type": "string",
                "description": (
                    "Add only: case-insensitive substring matched against "
                    "transaction merchant names (min 2 chars, e.g. 'wise')."
                ),
            },
        },
        "required": ["action", "name"],
    },
}
