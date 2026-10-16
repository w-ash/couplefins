from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.entities.transaction import Transaction
from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.filters import is_joint_row
from src.domain.formatting import FieldValue, field_str
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

from .finalization import assert_periods_not_finalized, months_of


async def fetch_and_validate(
    uow: UnitOfWorkProtocol, transaction_ids: list[UUID]
) -> dict[UUID, Transaction]:
    found = await uow.transactions.get_by_ids(transaction_ids)
    transactions: dict[UUID, Transaction] = {tx.id: tx for tx in found}
    missing = set(transaction_ids) - transactions.keys()
    if missing:
        raise NotFoundError(f"Transaction {next(iter(missing))} not found")

    await assert_periods_not_finalized(uow, months_of(transactions.values()))
    return transactions


def compute_edit(
    tx: Transaction,
    field_name: str,
    old_value: FieldValue,
    new_value: FieldValue,
    *,
    now: datetime | None = None,
    edited_by_person_id: UUID | None = None,
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
        edited_by_person_id=edited_by_person_id,
    )


# Why an edit or a link refuses a joint row, as `reject_joint_rows` reasons.
NO_PAYER_SPLIT = "A joint-account row has no payer split — set its owner shares"
NOT_A_SETTLEMENT_LEG = "A joint-account row cannot be a settlement leg"


def reject_joint_rows(transactions: Iterable[Transaction], reason: str) -> None:
    """Raise ValidationError(reason) if any row is a joint account's."""
    if any(is_joint_row(tx) for tx in transactions):
        raise ValidationError(reason)
