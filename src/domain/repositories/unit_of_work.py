from typing import Protocol, Self

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
from src.domain.repositories.upload_repository import UploadRepositoryProtocol


class UnitOfWorkProtocol(Protocol):
    @property
    def persons(self) -> PersonRepositoryProtocol: ...

    @property
    def transactions(self) -> TransactionRepositoryProtocol: ...

    @property
    def transaction_edits(self) -> TransactionEditRepositoryProtocol: ...

    @property
    def uploads(self) -> UploadRepositoryProtocol: ...

    @property
    def category_groups(self) -> CategoryGroupRepositoryProtocol: ...

    @property
    def categories(self) -> CategoryRepositoryProtocol: ...

    @property
    def category_group_budgets(self) -> CategoryGroupBudgetRepositoryProtocol: ...

    @property
    def reconciliation_periods(self) -> ReconciliationPeriodRepositoryProtocol: ...

    @property
    def settlements(self) -> SettlementRepositoryProtocol: ...

    @property
    def settlement_transaction_links(
        self,
    ) -> SettlementTransactionLinkRepositoryProtocol: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
