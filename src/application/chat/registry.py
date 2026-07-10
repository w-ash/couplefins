"""Single source of truth for the chat assistant's capability surface.

Every chat tool is declared here as a ToolSpec binding its JSON schema to its
propose/read handler, its confirmed-mutation executor (write tools only), and
the application use cases it exposes. The API tool list, the tool dispatch,
and the confirmation dispatch are all derived from REGISTRY — there is no
second place to keep in sync.

The parity contract: anything a human can do through the app, the chatbot can
do for them — and nothing more. The classification sets below make that
contract explicit and testable (see tests/unit/application/chat/
test_registry_parity.py): every use case in src/application/use_cases must be
reachable from a ToolSpec or explicitly accounted for as blacklisted
(human-only), mechanically excluded (file I/O), or internal plumbing.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from src.application.chat import confirmed_actions, tool_executor, tools
from src.application.chat.pending_actions import PendingAction
from src.domain.entities.person import Person
from src.domain.exceptions import ToolExecutionError

type ToolHandler = Callable[
    [dict[str, object], Person, list[Person]], Awaitable[dict[str, object]]
]
type ConfirmedExecutor = Callable[[PendingAction, Person], Awaitable[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One chat capability: schema + handler + parity accounting.

    A spec with an executor is a write tool (two-phase confirmation); one
    without is a read tool. Invariants are enforced at construction so an
    inconsistent spec cannot exist past import time.
    """

    name: str
    schema: Mapping[str, object]
    handler: ToolHandler
    use_cases: tuple[str, ...]
    executor: ConfirmedExecutor | None = None
    broadcast_entity: str | None = None

    def __post_init__(self) -> None:
        if self.name != self.schema["name"]:
            raise ValueError(
                f"ToolSpec {self.name!r} bound to schema {self.schema['name']!r}"
            )
        if (self.executor is None) != (self.broadcast_entity is None):
            raise ValueError(
                f"{self.name}: executor and broadcast_entity must be set together"
            )


REGISTRY: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="get_settlement_balance",
        schema=tools.GET_SETTLEMENT_BALANCE_SCHEMA,
        handler=tool_executor.handle_settlement_balance,
        use_cases=("GetSettleUpDataUseCase",),
    ),
    ToolSpec(
        name="get_budget_overview",
        schema=tools.GET_BUDGET_OVERVIEW_SCHEMA,
        handler=tool_executor.handle_budget_overview,
        use_cases=("GetBudgetOverviewUseCase",),
    ),
    ToolSpec(
        name="search_transactions",
        schema=tools.SEARCH_TRANSACTIONS_SCHEMA,
        handler=tool_executor.handle_search_transactions,
        use_cases=("SearchTransactionsUseCase",),
    ),
    ToolSpec(
        name="get_spending_by_group",
        schema=tools.GET_SPENDING_BY_GROUP_SCHEMA,
        handler=tool_executor.handle_spending_by_group,
        use_cases=("GetBudgetOverviewUseCase",),
    ),
    ToolSpec(
        name="get_spending_trends",
        schema=tools.GET_SPENDING_TRENDS_SCHEMA,
        handler=tool_executor.handle_spending_trends,
        use_cases=("GetSpendingTrendsUseCase",),
    ),
    ToolSpec(
        name="get_dashboard_status",
        schema=tools.GET_DASHBOARD_STATUS_SCHEMA,
        handler=tool_executor.handle_dashboard_status,
        use_cases=("GetSettleUpDataUseCase",),
    ),
    ToolSpec(
        name="get_tags",
        schema=tools.GET_TAGS_SCHEMA,
        handler=tool_executor.handle_get_tags,
        use_cases=("GetTagsUseCase",),
    ),
    ToolSpec(
        name="get_transaction_history",
        schema=tools.GET_TRANSACTION_HISTORY_SCHEMA,
        handler=tool_executor.handle_get_transaction_history,
        use_cases=("GetTransactionEditsUseCase",),
    ),
    ToolSpec(
        name="get_budgets",
        schema=tools.GET_BUDGETS_SCHEMA,
        handler=tool_executor.handle_get_budgets,
        use_cases=("list_budgets",),
    ),
    ToolSpec(
        name="get_category_setup",
        schema=tools.GET_CATEGORY_SETUP_SCHEMA,
        handler=tool_executor.handle_get_category_setup,
        use_cases=("ListUnmappedCategoriesUseCase",),
    ),
    ToolSpec(
        name="get_upload_history",
        schema=tools.GET_UPLOAD_HISTORY_SCHEMA,
        handler=tool_executor.handle_get_upload_history,
        use_cases=("GetUploadHistoryUseCase",),
    ),
    ToolSpec(
        name="get_reconciliation_report",
        schema=tools.GET_RECONCILIATION_REPORT_SCHEMA,
        handler=tool_executor.handle_get_reconciliation_report,
        use_cases=("GetReconciliationUseCase",),
    ),
    ToolSpec(
        name="get_settlement_activity",
        schema=tools.GET_SETTLEMENT_ACTIVITY_SCHEMA,
        handler=tool_executor.handle_get_settlement_activity,
        use_cases=(
            "FindSettlementCandidatesUseCase",
            "ListSettlementMerchantsUseCase",
        ),
    ),
    ToolSpec(
        name="get_dashboard_summary",
        schema=tools.GET_DASHBOARD_SUMMARY_SCHEMA,
        handler=tool_executor.handle_get_dashboard_summary,
        use_cases=("GetDashboardUseCase",),
    ),
    ToolSpec(
        name="get_adjustments_preview",
        schema=tools.GET_ADJUSTMENTS_PREVIEW_SCHEMA,
        handler=tool_executor.handle_get_adjustments_preview,
        use_cases=("PreviewAdjustmentsUseCase",),
    ),
    ToolSpec(
        name="update_budget",
        schema=tools.UPDATE_BUDGET_SCHEMA,
        handler=tool_executor.handle_update_budget,
        # UpdateBudgetUseCase (PUT /budgets/{id}) is covered by this tool's
        # upsert semantics via SaveBudgetUseCase — capability parity, not
        # endpoint parity.
        use_cases=("SaveBudgetUseCase", "UpdateBudgetUseCase"),
        executor=confirmed_actions.exec_budget,
        broadcast_entity="budgets",
    ),
    ToolSpec(
        name="update_transaction_split",
        schema=tools.UPDATE_TRANSACTION_SPLIT_SCHEMA,
        handler=tool_executor.handle_update_transaction_split,
        use_cases=("UpdateTransactionSplitsUseCase",),
        executor=confirmed_actions.exec_split,
        broadcast_entity="transactions",
    ),
    ToolSpec(
        name="bulk_update_transactions",
        schema=tools.BULK_UPDATE_TRANSACTIONS_SCHEMA,
        handler=tool_executor.handle_bulk_update_transactions,
        use_cases=("BulkUpdateTransactionsUseCase", "BulkModifyTagsUseCase"),
        executor=confirmed_actions.exec_bulk,
        broadcast_entity="transactions",
    ),
    ToolSpec(
        name="delete_budget",
        schema=tools.DELETE_BUDGET_SCHEMA,
        handler=tool_executor.handle_delete_budget,
        use_cases=("DeleteBudgetUseCase",),
        executor=confirmed_actions.exec_delete_budget,
        broadcast_entity="budgets",
    ),
    ToolSpec(
        name="copy_budgets",
        schema=tools.COPY_BUDGETS_SCHEMA,
        handler=tool_executor.handle_copy_budgets,
        use_cases=("CopyBudgetsUseCase",),
        executor=confirmed_actions.exec_copy_budgets,
        broadcast_entity="budgets",
    ),
    ToolSpec(
        name="manage_category_group",
        schema=tools.MANAGE_CATEGORY_GROUP_SCHEMA,
        handler=tool_executor.handle_manage_category_group,
        use_cases=(
            "CreateCategoryGroupUseCase",
            "UpdateCategoryGroupUseCase",
            "DeleteCategoryGroupUseCase",
        ),
        executor=confirmed_actions.exec_category_group,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="map_categories",
        schema=tools.MAP_CATEGORIES_SCHEMA,
        handler=tool_executor.handle_map_categories,
        use_cases=("BulkUpdateMappingsUseCase",),
        executor=confirmed_actions.exec_map_categories,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="set_category_personal",
        schema=tools.SET_CATEGORY_PERSONAL_SCHEMA,
        handler=tool_executor.handle_set_category_personal,
        use_cases=("UpdateCategoryUseCase",),
        executor=confirmed_actions.exec_category_personal,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="finalize_period",
        schema=tools.FINALIZE_PERIOD_SCHEMA,
        handler=tool_executor.handle_finalize_period,
        use_cases=("FinalizePeriodUseCase",),
        executor=confirmed_actions.exec_finalize,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="unfinalize_period",
        schema=tools.UNFINALIZE_PERIOD_SCHEMA,
        handler=tool_executor.handle_unfinalize_period,
        use_cases=("UnfinalizePeriodUseCase",),
        executor=confirmed_actions.exec_unfinalize,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="record_settlement",
        schema=tools.RECORD_SETTLEMENT_SCHEMA,
        handler=tool_executor.handle_record_settlement,
        use_cases=("RecordSettlementUseCase",),
        executor=confirmed_actions.exec_record_settlement,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="waive_settlement",
        schema=tools.WAIVE_SETTLEMENT_SCHEMA,
        handler=tool_executor.handle_waive_settlement,
        use_cases=("RecordWaivedSettlementUseCase",),
        executor=confirmed_actions.exec_waive_settlement,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="delete_settlement",
        schema=tools.DELETE_SETTLEMENT_SCHEMA,
        handler=tool_executor.handle_delete_settlement,
        use_cases=("DeleteSettlementUseCase",),
        executor=confirmed_actions.exec_delete_settlement,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="link_settlement_transaction",
        schema=tools.LINK_SETTLEMENT_TRANSACTION_SCHEMA,
        handler=tool_executor.handle_link_settlement_transaction,
        use_cases=("MarkTransactionAsSettlementUseCase",),
        executor=confirmed_actions.exec_link_settlement_tx,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="unlink_settlement_transaction",
        schema=tools.UNLINK_SETTLEMENT_TRANSACTION_SCHEMA,
        handler=tool_executor.handle_unlink_settlement_transaction,
        use_cases=("UnlinkSettlementTransactionUseCase",),
        executor=confirmed_actions.exec_unlink_settlement_tx,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="manage_settlement_merchant",
        schema=tools.MANAGE_SETTLEMENT_MERCHANT_SCHEMA,
        handler=tool_executor.handle_manage_settlement_merchant,
        use_cases=(
            "CreateSettlementMerchantUseCase",
            "DeleteSettlementMerchantUseCase",
        ),
        executor=confirmed_actions.exec_settlement_merchant,
        broadcast_entity="settlements",
    ),
)

_SPECS_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in REGISTRY}


def _build_tools() -> list[dict[str, object]]:
    """API tool list in registry order, cache breakpoint on the last entry.

    Order must be deterministic — tools render first in the prompt, so any
    reordering invalidates the whole prompt cache. Shallow copies keep the
    cache stamp off the schema constants.
    """
    tool_list = [dict(spec.schema) for spec in REGISTRY]
    tool_list[-1]["cache_control"] = {"type": "ephemeral"}
    return tool_list


TOOLS: list[dict[str, object]] = _build_tools()


async def execute_tool(
    name: str,
    tool_input: dict[str, object],
    current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    """Dispatch a tool call to its handler and return a summary dict."""
    spec = _SPECS_BY_NAME.get(name)
    if spec is None:
        raise ToolExecutionError(f"Unknown tool: {name}")
    try:
        return await spec.handler(tool_input, current_user, persons)
    except ToolExecutionError:
        raise
    except Exception as e:
        raise ToolExecutionError(f"Tool '{name}' failed: {e}") from e


async def execute_confirmed_action(
    action: PendingAction,
    current_user: Person,
) -> tuple[dict[str, object], str | None]:
    """Execute a confirmed pending action.

    Returns (result_summary, entity_to_broadcast).
    """
    spec = _SPECS_BY_NAME.get(action.tool_name)
    if spec is None or spec.executor is None:
        raise ValueError(f"Unknown mutation tool: {action.tool_name}")
    result = await spec.executor(action, current_user)
    return result, spec.broadcast_entity


# --- Parity accounting (asserted by test_registry_parity.py) ---

# Human-only by product decision: authentication, account lifecycle, and
# person preferences are never chatbot-operable.
BLACKLISTED_USE_CASES: frozenset[str] = frozenset({
    "LoginUseCase",
    "SetInitialPasswordUseCase",
    "ChangePasswordUseCase",
    "ResetPartnerPasswordUseCase",
    "SetupCoupleUseCase",
    "UpdatePersonUseCase",
})

# Excluded because chat has no file input/output channel, not by policy.
MECHANICALLY_EXCLUDED_USE_CASES: frozenset[str] = frozenset({
    "PreviewCsvUseCase",
    "UploadCsvUseCase",
    "ExportAdjustmentsUseCase",
})

# Plumbing the chat layer already consumes outside the tool loop (system
# prompt context, category-group name resolution) or startup-only seeding.
INTERNAL_USE_CASES: frozenset[str] = frozenset({
    "SeedCategoryGroupsUseCase",
    "SeedSettlementMerchantsUseCase",
    "ListPersonsUseCase",
    "ListCategoryGroupsUseCase",
})

# Parity is complete as of v1.8.2 — there is no pending bucket. A new use
# case must land in REGISTRY use_cases or one of the exclusion sets above,
# or the parity test fails. That is the point.
