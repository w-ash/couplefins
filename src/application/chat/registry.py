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
(human-only), mechanically excluded (file I/O), internal plumbing, or pending
a scheduled parity phase.
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
        name="update_budget",
        schema=tools.UPDATE_BUDGET_SCHEMA,
        handler=tool_executor.handle_update_budget,
        use_cases=("SaveBudgetUseCase",),
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

# Scheduled parity work. v1.8.1 ships the reads, v1.8.2 the writes; entries
# move into REGISTRY use_cases as their tools land. A use case appearing in
# neither this set nor any other bucket fails the parity test — that is the
# point.
PENDING_PARITY_USE_CASES: frozenset[str] = frozenset({
    # v1.8.1 — reads
    "GetTagsUseCase",
    "GetTransactionEditsUseCase",
    "list_budgets",
    "ListUnmappedCategoriesUseCase",
    "GetUploadHistoryUseCase",
    "GetReconciliationUseCase",
    "GetDashboardUseCase",
    "PreviewAdjustmentsUseCase",
    "FindSettlementCandidatesUseCase",
    "ListSettlementMerchantsUseCase",
    # v1.8.2 — writes
    "UpdateBudgetUseCase",
    "DeleteBudgetUseCase",
    "CopyBudgetsUseCase",
    "CreateCategoryGroupUseCase",
    "UpdateCategoryGroupUseCase",
    "DeleteCategoryGroupUseCase",
    "BulkUpdateMappingsUseCase",
    "UpdateCategoryUseCase",
    "FinalizePeriodUseCase",
    "UnfinalizePeriodUseCase",
    "RecordSettlementUseCase",
    "RecordWaivedSettlementUseCase",
    "DeleteSettlementUseCase",
    "MarkTransactionAsSettlementUseCase",
    "UnlinkSettlementTransactionUseCase",
    "CreateSettlementMerchantUseCase",
    "DeleteSettlementMerchantUseCase",
})
