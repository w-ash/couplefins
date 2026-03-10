from typing import Protocol

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
from src.domain.repositories.upload_repository import UploadRepositoryProtocol


class UnitOfWorkProtocol(Protocol):
    @property
    def persons(self) -> PersonRepositoryProtocol: ...

    @property
    def transactions(self) -> TransactionRepositoryProtocol: ...

    @property
    def uploads(self) -> UploadRepositoryProtocol: ...

    @property
    def category_groups(self) -> CategoryGroupRepositoryProtocol: ...

    @property
    def category_mappings(self) -> CategoryMappingRepositoryProtocol: ...

    @property
    def category_group_budgets(self) -> CategoryGroupBudgetRepositoryProtocol: ...

    @property
    def reconciliation_periods(self) -> ReconciliationPeriodRepositoryProtocol: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
