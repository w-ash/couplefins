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
from typing import Literal, cast

from src.application.chat import confirmed_actions, tool_executor, tools
from src.application.chat.pending_actions import PendingAction
from src.application.chat.protocols import ToolContext
from src.application.chat.subagent import run_subagent
from src.application.chat.user_data import strip_user_data
from src.config.settings import get_settings
from src.domain.entities.person import Person
from src.domain.exceptions import ToolExecutionError

type ToolKind = Literal["read", "write", "agentic"]
type ToolHandler = Callable[
    [dict[str, object], ToolContext], Awaitable[dict[str, object]]
]
type ConfirmedExecutor = Callable[[PendingAction, Person], Awaitable[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One chat capability: schema + handler + parity accounting.

    Kind is explicit: "read" tools answer queries, "write" tools propose
    two-phase mutations (executor + broadcast required), "agentic" tools are
    capabilities rather than queries (code execution, delegation) — they may
    be server-executed, in which case they carry no handler. Invariants are
    enforced at construction so an inconsistent spec cannot exist past
    import time.
    """

    name: str
    schema: Mapping[str, object]
    handler: ToolHandler | None
    use_cases: tuple[str, ...]
    kind: ToolKind = "read"
    executor: ConfirmedExecutor | None = None
    broadcast_entity: str | None = None
    # Deferred tools stay out of the prompt until tool search surfaces them.
    # Deferred is the default so new tools stay cheap; only the hot tools
    # (observed traffic) and agentic capabilities load up front.
    defer_loading: bool = True

    def __post_init__(self) -> None:
        if self.name != self.schema["name"]:
            raise ValueError(
                f"ToolSpec {self.name!r} bound to schema {self.schema['name']!r}"
            )
        if (self.kind == "write") != (self.executor is not None):
            raise ValueError(
                f"{self.name}: kind {self.kind!r} inconsistent with executor"
            )
        if (self.executor is None) != (self.broadcast_entity is None):
            raise ValueError(
                f"{self.name}: executor and broadcast_entity must be set together"
            )
        if self.handler is None and self.kind != "agentic":
            raise ValueError(
                f"{self.name}: only agentic server tools may omit a handler"
            )
        if self.kind == "agentic" and self.defer_loading:
            raise ValueError(
                f"{self.name}: agentic capabilities must not be deferred — "
                "the model under-reaches for them as it is"
            )


# Lives here (not tool_executor.py) because it needs the registry's read
# toolset and executor: tool_executor is imported BY this module, so putting
# it there would create a cycle. Name resolution of REGISTRY/execute_tool
# happens at call time, after this module is fully loaded.
async def _handle_delegate_analysis(
    tool_input: dict[str, object], ctx: ToolContext
) -> dict[str, object]:
    question = str(tool_input.get("question", "")).strip()
    if not question:
        raise ToolExecutionError("question is required")
    scope = tool_input.get("scope")
    return await run_subagent(
        question,
        str(scope) if scope is not None else None,
        ctx,
        tools=build_subagent_tools(),
        execute_fn=execute_tool,
        cfg=get_settings().chat,
    )


REGISTRY: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="get_settlement_balance",
        schema=tools.GET_SETTLEMENT_BALANCE_SCHEMA,
        handler=tool_executor.handle_settlement_balance,
        use_cases=("GetSettleUpDataUseCase",),
        defer_loading=False,
    ),
    ToolSpec(
        name="get_budget_overview",
        schema=tools.GET_BUDGET_OVERVIEW_SCHEMA,
        handler=tool_executor.handle_budget_overview,
        use_cases=("GetBudgetOverviewUseCase",),
        defer_loading=False,
    ),
    ToolSpec(
        name="search_transactions",
        schema=tools.SEARCH_TRANSACTIONS_SCHEMA,
        handler=tool_executor.handle_search_transactions,
        use_cases=("SearchTransactionsUseCase",),
        defer_loading=False,
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
        kind="write",
        executor=confirmed_actions.exec_budget,
        broadcast_entity="budgets",
    ),
    ToolSpec(
        name="update_transaction_split",
        schema=tools.UPDATE_TRANSACTION_SPLIT_SCHEMA,
        handler=tool_executor.handle_update_transaction_split,
        use_cases=("UpdateTransactionSplitsUseCase",),
        kind="write",
        executor=confirmed_actions.exec_split,
        broadcast_entity="transactions",
    ),
    ToolSpec(
        name="bulk_update_transactions",
        schema=tools.BULK_UPDATE_TRANSACTIONS_SCHEMA,
        handler=tool_executor.handle_bulk_update_transactions,
        use_cases=("BulkUpdateTransactionsUseCase", "BulkModifyTagsUseCase"),
        kind="write",
        executor=confirmed_actions.exec_bulk,
        broadcast_entity="transactions",
    ),
    ToolSpec(
        name="delete_budget",
        schema=tools.DELETE_BUDGET_SCHEMA,
        handler=tool_executor.handle_delete_budget,
        use_cases=("DeleteBudgetUseCase",),
        kind="write",
        executor=confirmed_actions.exec_delete_budget,
        broadcast_entity="budgets",
    ),
    ToolSpec(
        name="copy_budgets",
        schema=tools.COPY_BUDGETS_SCHEMA,
        handler=tool_executor.handle_copy_budgets,
        use_cases=("CopyBudgetsUseCase",),
        kind="write",
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
        kind="write",
        executor=confirmed_actions.exec_category_group,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="map_categories",
        schema=tools.MAP_CATEGORIES_SCHEMA,
        handler=tool_executor.handle_map_categories,
        use_cases=("BulkUpdateMappingsUseCase",),
        kind="write",
        executor=confirmed_actions.exec_map_categories,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="set_category_personal",
        schema=tools.SET_CATEGORY_PERSONAL_SCHEMA,
        handler=tool_executor.handle_set_category_personal,
        use_cases=("UpdateCategoryUseCase",),
        kind="write",
        executor=confirmed_actions.exec_category_personal,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="finalize_period",
        schema=tools.FINALIZE_PERIOD_SCHEMA,
        handler=tool_executor.handle_finalize_period,
        use_cases=("FinalizePeriodUseCase",),
        kind="write",
        executor=confirmed_actions.exec_finalize,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="unfinalize_period",
        schema=tools.UNFINALIZE_PERIOD_SCHEMA,
        handler=tool_executor.handle_unfinalize_period,
        use_cases=("UnfinalizePeriodUseCase",),
        kind="write",
        executor=confirmed_actions.exec_unfinalize,
        broadcast_entity="reconciliation",
    ),
    ToolSpec(
        name="record_settlement",
        schema=tools.RECORD_SETTLEMENT_SCHEMA,
        handler=tool_executor.handle_record_settlement,
        use_cases=("RecordSettlementUseCase",),
        kind="write",
        executor=confirmed_actions.exec_record_settlement,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="waive_settlement",
        schema=tools.WAIVE_SETTLEMENT_SCHEMA,
        handler=tool_executor.handle_waive_settlement,
        use_cases=("RecordWaivedSettlementUseCase",),
        kind="write",
        executor=confirmed_actions.exec_waive_settlement,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="delete_settlement",
        schema=tools.DELETE_SETTLEMENT_SCHEMA,
        handler=tool_executor.handle_delete_settlement,
        use_cases=("DeleteSettlementUseCase",),
        kind="write",
        executor=confirmed_actions.exec_delete_settlement,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="link_settlement_transaction",
        schema=tools.LINK_SETTLEMENT_TRANSACTION_SCHEMA,
        handler=tool_executor.handle_link_settlement_transaction,
        use_cases=("MarkTransactionAsSettlementUseCase",),
        kind="write",
        executor=confirmed_actions.exec_link_settlement_tx,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="unlink_settlement_transaction",
        schema=tools.UNLINK_SETTLEMENT_TRANSACTION_SCHEMA,
        handler=tool_executor.handle_unlink_settlement_transaction,
        use_cases=("UnlinkSettlementTransactionUseCase",),
        kind="write",
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
        kind="write",
        executor=confirmed_actions.exec_settlement_merchant,
        broadcast_entity="settlements",
    ),
    ToolSpec(
        name="code_execution",
        schema=tools.CODE_EXECUTION_SCHEMA,
        handler=None,
        use_cases=(),
        kind="agentic",
        defer_loading=False,
    ),
    ToolSpec(
        name="delegate_analysis",
        schema=tools.DELEGATE_ANALYSIS_SCHEMA,
        handler=_handle_delegate_analysis,
        use_cases=(),
        kind="agentic",
        defer_loading=False,
    ),
    ToolSpec(
        name="tool_search_tool_bm25",
        schema=tools.TOOL_SEARCH_SCHEMA,
        handler=None,
        use_cases=(),
        kind="agentic",
        defer_loading=False,
    ),
)

_SPECS_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in REGISTRY}

# Read tools are callable both directly and from the sandbox. Listing both
# callers deviates from the docs' pick-one guidance on purpose: direct calls
# answer one-shot questions without container spin-up, programmatic calls
# let sandbox code aggregate large results. Write and agentic tools NEVER
# get allowed_callers — mutations stay two-phase behind human confirmation,
# and delegation stays a top-level decision.
_READ_ALLOWED_CALLERS: tuple[str, ...] = ("direct", "code_execution_20260120")


def _stamp_cache(tools_out: list[dict[str, object]], idx: int) -> None:
    """Stamp the ephemeral cache breakpoint on ``tools_out[idx]``.

    A no-op for ``idx < 0`` (empty tier), so callers can pass
    ``len(tier) - 1`` unconditionally.
    """
    if idx >= 0:
        tools_out[idx]["cache_control"] = {"type": "ephemeral"}


# --- Page-contextual tool routing (v1.9.0) ---------------------------------
#
# Rule-based context routing: the web client sends the coarse UI section the
# user is on, and the deferred read tools relevant to that section are
# promoted into the loaded set. Rule-based (not semantic) is the right call
# at this scale — below ~50 tools a validated rule map is deterministic,
# free, and more accurate than a retriever, and a UI route is the cleanest
# domain signal there is. Each page's promotions ride a dedicated cache
# breakpoint (the promoted segment in ``build_tools``), so the invariant
# core stays cached across navigation while a section's tools cache across
# that section's turns.
#
# Canonical page keys — the backend is the source of truth; the web client's
# SECTION_BY_SEGMENT map (web/src/components/chat/ChatPanel.tsx) mirrors
# this set and is kept in sync by hand. Unknown/absent pages promote
# nothing. The mobile full-screen chat page (/ask) and /account are
# deliberately unmapped — there is no domain signal on the chat page itself.
_CANONICAL_PAGES: frozenset[str] = frozenset({
    "dashboard",
    "transactions",
    "settle",
    "budget",
    "insights",
    "upload",
    "settings",
})

_PAGE_TOOL_HINTS: Mapping[str, tuple[str, ...]] = {
    "dashboard": ("get_dashboard_summary", "get_dashboard_status"),
    "transactions": ("get_transaction_history", "get_tags"),
    "settle": ("get_settlement_activity", "get_adjustments_preview"),
    "budget": ("get_budgets", "get_spending_by_group"),
    "insights": ("get_spending_trends", "get_spending_by_group"),
    "upload": ("get_upload_history", "get_reconciliation_report"),
    "settings": ("get_category_setup", "get_tags"),
}

# The per-page promotion ceiling, DERIVED not hand-set: the loaded set must
# stay under the ~10-tool accuracy ceiling, and everything not deferred (the
# invariant prefix plus the agentic server blocks) is always loaded, so a
# page may promote at most ``10 - <always-loaded>`` deferred reads.
_TOOL_CEILING = 10
_MAX_PROMOTED_PER_PAGE = _TOOL_CEILING - sum(1 for s in REGISTRY if not s.defer_loading)


def _validate_page_hints(
    hints: Mapping[str, tuple[str, ...]] | None = None,
) -> None:
    """Fail at import if the hint map drifts from the registry.

    Same posture as ``ToolSpec.__post_init__``: an invalid routing table
    cannot exist past import. Guards the three ways the hand-maintained map
    rots — an unknown page key, a tool name that no longer exists (or
    stopped being a deferred read), and silent breach of the derived
    per-page ceiling. ``hints`` defaults to the module map; tests pass bad
    maps directly.
    """
    if hints is None:
        hints = _PAGE_TOOL_HINTS
    for page, names in hints.items():
        if page not in _CANONICAL_PAGES:
            raise ValueError(
                f"_PAGE_TOOL_HINTS: {page!r} is not a canonical page "
                f"({sorted(_CANONICAL_PAGES)})"
            )
        if len(names) > _MAX_PROMOTED_PER_PAGE:
            raise ValueError(
                f"_PAGE_TOOL_HINTS[{page!r}]: promotes {len(names)} tools, "
                f"exceeds the derived ceiling of {_MAX_PROMOTED_PER_PAGE}"
            )
        for name in names:
            spec = _SPECS_BY_NAME.get(name)
            if spec is None:
                raise ValueError(f"_PAGE_TOOL_HINTS[{page!r}]: unknown tool {name!r}")
            if not spec.defer_loading:
                raise ValueError(
                    f"_PAGE_TOOL_HINTS[{page!r}]: {name!r} is already loaded "
                    "(not deferred) — promoting it is a no-op that wastes budget"
                )
            if spec.kind != "read":
                raise ValueError(
                    f"_PAGE_TOOL_HINTS[{page!r}]: {name!r} is {spec.kind!r}; "
                    "only deferred reads may be promoted"
                )


_validate_page_hints()


def _promoted_tool_names(page: str | None) -> frozenset[str]:
    """Deferred read tools to load eagerly for the user's current UI section.

    Unknown or absent pages promote nothing — the surface degrades cleanly
    to the static core plus tool-search discovery.
    """
    return frozenset(_PAGE_TOOL_HINTS.get(page or "", ()))


def build_tools(
    *, enable_code_execution: bool = True, page: str | None = None
) -> list[dict[str, object]]:
    """Anthropic tool list in three cache tiers: prefix, promoted, rest.

    - **prefix** — the always-hot curated core (the hot reads plus
      delegate_analysis). Page-INVARIANT and byte-stable; its last entry
      carries the primary tools breakpoint, so navigating between UI
      sections never invalidates it.
    - **promoted** — the deferred reads ``page`` surfaces for the current
      section (see ``_PAGE_TOOL_HINTS``). Carries its own breakpoint, so a
      section's tools cache across that section's turns and only this
      segment is rewritten on navigation. Empty (no breakpoint) when the
      page promotes nothing.
    - **rest** — the raw ``{type, name}`` server-tool blocks (which reject a
      cache stamp — the pre-v1.9.0 placement on tool_search was invalid)
      and the deferred pool surfaced on demand via tool search. Uncached.

    Order within each tier follows registry order (deterministic —
    reordering invalidates the cache). Shallow copies keep stamps off the
    schema constants.

    CACHE-BREAKPOINT BUDGET (API cap: 4, fully spent — never add a fifth):
    tools prefix (1) + promoted segment (1, promoting pages only) + system
    primer (1, system_prompt.py) + incremental message stamp (1,
    anthropic_adapter.py).
    """
    promoted_names = _promoted_tool_names(page)
    prefix: list[dict[str, object]] = []  # always-hot, cached, page-invariant
    promoted: list[dict[str, object]] = []  # page-promoted reads, cached per page
    rest: list[dict[str, object]] = []  # server blocks + deferred pool, uncached
    for spec in REGISTRY:
        if spec.name == "code_execution" and not enable_code_execution:
            continue
        tool = dict(spec.schema)
        if spec.handler is None:  # raw server-tool block (agentic, API-owned)
            rest.append(tool)
            continue
        if enable_code_execution and spec.kind == "read":
            tool["allowed_callers"] = list(_READ_ALLOWED_CALLERS)
        if not spec.defer_loading:
            prefix.append(tool)  # curated core + dispatched agentic
        elif spec.name in promoted_names:
            promoted.append(tool)  # loaded + cached for this section
        else:
            tool["defer_loading"] = True
            rest.append(tool)  # deferred: discovered via tool search
    _stamp_cache(prefix, len(prefix) - 1)
    _stamp_cache(promoted, len(promoted) - 1)  # no-op when nothing promoted
    return prefix + promoted + rest


def build_subagent_tools() -> list[dict[str, object]]:
    """Read-only toolset for the research subagent.

    No mutations, no code execution, no nested delegate_analysis (one level
    of delegation only), and no allowed_callers — the subagent has no
    sandbox to call from.
    """
    tool_list = [dict(spec.schema) for spec in REGISTRY if spec.kind == "read"]
    tool_list[-1]["cache_control"] = {"type": "ephemeral"}
    return tool_list


async def execute_tool(
    name: str,
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    """Dispatch a tool call to its handler and return a summary dict."""
    spec = _SPECS_BY_NAME.get(name)
    if spec is None:
        raise ToolExecutionError(f"Unknown tool: {name}")
    if spec.handler is None:
        raise ToolExecutionError(f"Tool '{name}' executes server-side")
    # Input sanitizer: the model may echo user_data-wrapped values back
    # as tool inputs — strip the tags here (the single dispatch point) so
    # they can never break lookups or persist into stored tool_input.
    tool_input = cast(dict[str, object], strip_user_data(tool_input))
    try:
        return await spec.handler(tool_input, ctx)
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
