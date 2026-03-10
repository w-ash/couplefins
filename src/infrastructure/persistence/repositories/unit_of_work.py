from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.category_group_budget_repository import (
    CategoryGroupBudgetRepository,
)
from src.infrastructure.persistence.repositories.category_group_repository import (
    CategoryGroupRepository,
)
from src.infrastructure.persistence.repositories.category_mapping_repository import (
    CategoryMappingRepository,
)
from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from src.infrastructure.persistence.repositories.reconciliation_period_repository import (
    ReconciliationPeriodRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from src.infrastructure.persistence.repositories.upload_repository import (
    UploadRepository,
)


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.persons = PersonRepository(session)
        self.transactions = TransactionRepository(session)
        self.uploads = UploadRepository(session)
        self.category_groups = CategoryGroupRepository(session)
        self.category_mappings = CategoryMappingRepository(session)
        self.category_group_budgets = CategoryGroupBudgetRepository(session)
        self.reconciliation_periods = ReconciliationPeriodRepository(session)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
