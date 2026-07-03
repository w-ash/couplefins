from unittest.mock import AsyncMock

from src.domain.repositories.category_group_budget_repository import (
    CategoryGroupBudgetRepositoryProtocol,
)
from src.domain.repositories.category_group_repository import (
    CategoryGroupRepositoryProtocol,
)
from src.domain.repositories.category_repository import (
    CategoryRepositoryProtocol,
)
from src.domain.repositories.person_repository import PersonRepositoryProtocol
from src.domain.repositories.reconciliation_period_repository import (
    ReconciliationPeriodRepositoryProtocol,
)
from src.domain.repositories.settlement_merchant_repository import (
    SettlementMerchantRepositoryProtocol,
)
from src.domain.repositories.settlement_repository import (
    SettlementRepositoryProtocol,
)
from src.domain.repositories.settlement_transaction_link_repository import (
    SettlementTransactionLinkRepositoryProtocol,
)
from src.domain.repositories.transaction_edit_repository import (
    TransactionEditRepositoryProtocol,
)
from src.domain.repositories.transaction_repository import TransactionRepositoryProtocol
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.repositories.upload_repository import UploadRepositoryProtocol


def make_mock_uow() -> AsyncMock:
    uow = AsyncMock(spec=UnitOfWorkProtocol)
    uow.persons = AsyncMock(spec=PersonRepositoryProtocol)
    uow.transactions = AsyncMock(spec=TransactionRepositoryProtocol)
    uow.transaction_edits = AsyncMock(spec=TransactionEditRepositoryProtocol)
    uow.uploads = AsyncMock(spec=UploadRepositoryProtocol)
    uow.category_groups = AsyncMock(spec=CategoryGroupRepositoryProtocol)
    uow.categories = AsyncMock(spec=CategoryRepositoryProtocol)
    uow.category_group_budgets = AsyncMock(spec=CategoryGroupBudgetRepositoryProtocol)
    uow.reconciliation_periods = AsyncMock(spec=ReconciliationPeriodRepositoryProtocol)
    uow.settlement_merchants = AsyncMock(spec=SettlementMerchantRepositoryProtocol)
    uow.settlement_merchants.get_all.return_value = []
    uow.settlement_merchants.count.return_value = 0
    uow.settlements = AsyncMock(spec=SettlementRepositoryProtocol)
    uow.settlement_transaction_links = AsyncMock(
        spec=SettlementTransactionLinkRepositoryProtocol
    )
    uow.settlement_transaction_links.get_by_transaction_id.return_value = []
    uow.reconciliation_periods.get_by_period.return_value = None
    uow.reconciliation_periods.get_by_periods.return_value = []
    uow.reconciliation_periods.get_by_year.return_value = []
    uow.settlements.get_by_year.return_value = []
    uow.transactions.get_settlement_relevant_by_date_range.return_value = []
    return uow


def set_passthrough_save(uow_mock: AsyncMock) -> None:
    """Configure settlements.save to return the entity as-is."""
    uow_mock.settlements.save = AsyncMock(side_effect=lambda entity: entity)
