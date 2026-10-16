from attrs import define

from src.domain.entities.account import Account
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListAccountsCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class ListAccountsResult:
    accounts: list[Account]


@define(slots=True)
class ListAccountsUseCase:
    async def execute(
        self, _command: ListAccountsCommand, uow: UnitOfWorkProtocol
    ) -> ListAccountsResult:
        """Every account, by label: each partner's personal account and the
        joint accounts."""
        async with uow:
            accounts = await uow.accounts.get_all()
            return ListAccountsResult(
                accounts=sorted(accounts, key=lambda a: (a.name, a.kind))
            )
