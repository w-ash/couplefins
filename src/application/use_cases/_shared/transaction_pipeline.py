from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.constants import SplitDefaults
from src.domain.entities.transaction import Transaction
from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.formatting import FieldValue, field_str
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

from .finalization import assert_periods_not_finalized


async def fetch_and_validate(
    uow: UnitOfWorkProtocol, transaction_ids: list[UUID]
) -> dict[UUID, Transaction]:
    found = await uow.transactions.get_by_ids(transaction_ids)
    transactions: dict[UUID, Transaction] = {tx.id: tx for tx in found}
    missing = set(transaction_ids) - transactions.keys()
    if missing:
        raise NotFoundError(f"Transaction {next(iter(missing))} not found")

    affected_periods = {(tx.date.year, tx.date.month) for tx in transactions.values()}
    await assert_periods_not_finalized(uow, affected_periods)
    return transactions


def compute_edit(
    tx: Transaction,
    field_name: str,
    old_value: FieldValue,
    new_value: FieldValue,
    now: datetime | None = None,
) -> TransactionEdit | None:
    if old_value == new_value:
        return None
    if now is None:
        now = datetime.now(UTC)
    return TransactionEdit(
        id=uuid4(),
        transaction_id=tx.id,
        field_name=field_name,
        old_value=field_str(old_value),
        new_value=field_str(new_value),
        edited_at=now,
    )


def validate_payer_percentage(pct: int) -> None:
    if not (0 <= pct <= SplitDefaults.MAX_PAYER_PERCENTAGE):
        raise ValidationError(
            f"payer_percentage must be 0-{SplitDefaults.MAX_PAYER_PERCENTAGE}, "
            f"got {pct}"
        )
