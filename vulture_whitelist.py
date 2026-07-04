"""Vulture whitelist — false positives that survive config-level suppression.

Each entry explains why the code appears unused to Vulture but is consumed
at runtime by a framework, serialization, or test harness.
"""

# --- StrEnum members: consumed via Pydantic serialization/deserialization ---

from src.application.use_cases.bulk_modify_tags import TagAction

TagAction.REMOVE  # deserialized from API request body

# --- Auth result fields: constructed in use case, consumed by route handler ---

from src.application.use_cases.auth.change_password import ChangePasswordResult
from src.application.use_cases.auth.reset_partner_password import (
    ResetPartnerPasswordResult,
)

ChangePasswordResult.success  # returned from change-password use case
ResetPartnerPasswordResult.success  # returned from reset-partner-password use case

# --- attrs Result fields: constructed in use case, consumed by caller ---

from src.application.use_cases.seed_category_groups import SeedCategoryGroupsResult

SeedCategoryGroupsResult.groups_created  # returned from startup seeder
SeedCategoryGroupsResult.categories_created
SeedCategoryGroupsResult.skipped

from src.application.use_cases.seed_settlement_merchants import (
    SeedSettlementMerchantsResult,
)

SeedSettlementMerchantsResult.merchants_created  # returned from startup seeder
SeedSettlementMerchantsResult.skipped

# --- Pydantic BaseModel fields: serialized to JSON by FastAPI ---

from src.interface.api.schemas.dashboard import DashboardResponse

DashboardResponse.current_month_year  # response fields — serialized, never accessed as attributes
DashboardResponse.current_month_month
DashboardResponse.current_month_total_household_spending
DashboardResponse.current_month_net_household_spending
DashboardResponse.current_month_transaction_count
DashboardResponse.current_month_person_summaries
DashboardResponse.current_month_settlement

from src.interface.api.schemas.auth import AuthPersonResponse

AuthPersonResponse.has_password  # serialized to JSON in GET /auth/persons

from src.interface.api.routes.health import HealthResponse

HealthResponse.version  # serialized to JSON in GET /health
HealthResponse.schema_version
HealthResponse.schema_ok
HealthResponse.database_host
HealthResponse.database_mode
HealthResponse.chat_available

# --- Domain value objects: attrs fields accessed by callers ---

from src.domain.entities.import_event import ImportEvent

ImportEvent.imported_at  # accessed by route handler + tests

# --- Pydantic schema fields: serialized to JSON ---

from src.interface.api.schemas.transactions import ImportEventResponse

ImportEventResponse.imported_at  # serialized to JSON in GET /transactions/{id}/edits

# --- Domain functions: tested + public API, not yet wired into a use case ---

from src.domain.export.adjustments import assert_adjustments_zero_sum
from src.domain.insights import compute_trailing_average

assert_adjustments_zero_sum  # zero-sum invariant, tested in test_adjustments.py
compute_trailing_average  # tested in test_insights.py, planned for future Insights enhancements
# --- Pydantic model validators: invoked by Pydantic framework ---

from src.interface.api.schemas.chat import ChatRequest

ChatRequest._check_total_content_size  # @model_validator called by Pydantic

# --- Test-only utility: called from tests/integration/conftest.py ---

from src.config.settings import reset_settings

reset_settings  # resets settings cache between tests

# --- Pydantic BaseModel fields: serialized to JSON by FastAPI ---

from src.interface.api.schemas.settlements import (
    PayerGroupSplitSummaryResponse,
    PayerSplitSummaryResponse,
)

PayerSplitSummaryResponse.fronted  # serialized in GET /settle-up
PayerSplitSummaryResponse.their_share
PayerSplitSummaryResponse.partner_share
PayerGroupSplitSummaryResponse.fronted
PayerGroupSplitSummaryResponse.their_share
PayerGroupSplitSummaryResponse.partner_share

# --- Settlement ledger domain API: tested in test_ledger.py ---
# consumed by v1.7.5 handoff 2 (use-case wiring) — remove there

from src.domain.ledger import LedgerMonth, SettlementLedger, compute_ledger

compute_ledger  # entry point for the GetSettleUpData rewiring
LedgerMonth.covering_settlement_ids  # payment attribution for the month rows
LedgerMonth.is_offset  # month-acted-as-credit marker for the month rows
SettlementLedger.outstanding  # hero total for Settle Up / dashboard
SettlementLedger.unapplied_payment_total  # overpayment/reverse-payment credit
SettlementLedger.span  # covered-months span for the hero card

# --- TypedDict fields: consumed by type checker + dict access ---

from src.application.chat.voices import VoiceDict

VoiceDict.identity  # accessed via dict["identity"] in system_prompt.py
VoiceDict.voice_examples  # accessed via dict["voice_examples"] in system_prompt.py
VoiceDict.rules  # accessed via dict["rules"] in system_prompt.py
