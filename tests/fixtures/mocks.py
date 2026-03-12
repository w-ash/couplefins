from unittest.mock import AsyncMock

from src.domain.repositories.category_group_budget_repository import (
    CategoryGroupBudgetRepositoryProtocol,
)
from src.domain.repositories.category_group_repository import (
    CategoryGroupRepositoryProtocol,
)
from src.domain.repositories.category_mapping_repository import (
    CategoryMappingRepositoryProtocol,
)
from src.domain.repositories.person_repository import PersonRepositoryProtocol
from src.domain.repositories.reconciliation_period_repository import (
    ReconciliationPeriodRepositoryProtocol,
)
from src.domain.repositories.transaction_repository import TransactionRepositoryProtocol
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.repositories.upload_repository import UploadRepositoryProtocol


def make_mock_uow() -> AsyncMock:
    uow = AsyncMock(spec=UnitOfWorkProtocol)
    uow.persons = AsyncMock(spec=PersonRepositoryProtocol)
    uow.transactions = AsyncMock(spec=TransactionRepositoryProtocol)
    uow.uploads = AsyncMock(spec=UploadRepositoryProtocol)
    uow.category_groups = AsyncMock(spec=CategoryGroupRepositoryProtocol)
    uow.category_mappings = AsyncMock(spec=CategoryMappingRepositoryProtocol)
    uow.category_group_budgets = AsyncMock(spec=CategoryGroupBudgetRepositoryProtocol)
    uow.reconciliation_periods = AsyncMock(spec=ReconciliationPeriodRepositoryProtocol)
    uow.reconciliation_periods.get_by_period.return_value = None
    uow.reconciliation_periods.get_by_year.return_value = []
    return uow
