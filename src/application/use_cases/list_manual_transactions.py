from attrs import define

from src.application.use_cases._shared.transaction_reads import fetch_account_rows
from src.application.use_cases._shared.transactions import manual_accounts
from src.domain.entities.transaction import Transaction
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListManualTransactionsCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class ListManualTransactionsResult:
    transactions: list[Transaction]  # newest first


@define(slots=True)
class ListManualTransactionsUseCase:
    async def execute(
        self, _command: ListManualTransactionsCommand, uow: UnitOfWorkProtocol
    ) -> ListManualTransactionsResult:
        """Every hand-entered row: the rows of the hand-entered accounts,
        newest first. Rows of the same date order by id."""
        async with uow:
            accounts = await manual_accounts(uow, await uow.accounts.get_all())
            rows = await fetch_account_rows(uow, [a.id for a in accounts])
            return ListManualTransactionsResult(
                transactions=sorted(rows, key=lambda tx: (-tx.date.toordinal(), tx.id))
            )
