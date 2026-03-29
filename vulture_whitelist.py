"""Vulture whitelist — false positives that survive config-level suppression.

Each entry explains why the code appears unused to Vulture but is consumed
at runtime by a framework, serialization, or test harness.
"""

# --- StrEnum members: consumed via Pydantic serialization/deserialization ---

from src.application.use_cases.bulk_modify_tags import TagAction

TagAction.REMOVE  # deserialized from API request body

from src.domain.entities.settlement import SettlementMethod

SettlementMethod.VENMO  # deserialized from API request + used in test factories
SettlementMethod.ZELLE  # valid settlement method, serialized to API
SettlementMethod.OTHER  # valid settlement method, serialized to API

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

# --- Pydantic BaseModel fields: serialized to JSON by FastAPI ---

from src.interface.api.schemas.dashboard import DashboardResponse

DashboardResponse.current_month_year  # response fields — serialized, never accessed as attributes
DashboardResponse.current_month_month
DashboardResponse.current_month_total_shared_spending
DashboardResponse.current_month_net_shared_spending
DashboardResponse.current_month_transaction_count
DashboardResponse.current_month_person_summaries
DashboardResponse.current_month_settlement

from src.interface.api.schemas.auth import AuthPersonResponse

AuthPersonResponse.has_password  # serialized to JSON in GET /auth/persons

# --- Domain functions: tested + public API, not yet wired into a use case ---

from src.domain.insights import compute_trailing_average

compute_trailing_average  # tested in test_insights.py, planned for future Insights enhancements

# --- Test-only utility: called from tests/integration/conftest.py ---

from src.config.settings import reset_settings

reset_settings  # resets settings cache between tests
