from collections.abc import Sequence
from uuid import UUID

from attrs import define

from src.application.use_cases._shared.transactions import (
    delete_transactions_with_links,
    load_rows_to_move,
)
from src.domain.dedup import TransactionNaturalKey, natural_key
from src.domain.entities.account import Account, joint_account_id, personal_account_id
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import Upload
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.joint import as_joint_row
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class MarkAccountJointCommand:
    label: str


@define(frozen=True, slots=True)
class MarkAccountJointResult:
    account: Account
    moved_count: int
    dropped_count: int


def _collapse_twins(
    rows: Sequence[Transaction], uploads: dict[UUID, Upload]
) -> tuple[list[Transaction], list[Transaction]]:
    """Split rows into (kept, dropped). Rows that share a natural key are
    one bank row imported by both partners; the older upload's row is kept."""
    oldest_first = sorted(
        rows, key=lambda tx: (uploads[tx.upload_id].uploaded_at, str(tx.id))
    )
    kept: dict[TransactionNaturalKey, Transaction] = {}
    dropped: list[Transaction] = []
    for tx in oldest_first:
        key = natural_key(tx)
        if key in kept:
            dropped.append(tx)
        else:
            kept[key] = tx
    return list(kept.values()), dropped


async def _assert_no_settlement_legs(
    uow: UnitOfWorkProtocol, rows: Sequence[Transaction], label: str
) -> None:
    links = await uow.settlement_transaction_links.get_by_transaction_ids([
        tx.id for tx in rows
    ])
    if links:
        raise ValidationError(
            f"{len(links)} row(s) under {label} are linked to a settlement; "
            "unlink them first. A joint-account row cannot be a settlement leg."
        )


@define(slots=True)
class MarkAccountJointUseCase:
    async def execute(
        self, command: MarkAccountJointCommand, uow: UnitOfWorkProtocol
    ) -> MarkAccountJointResult:
        """Make a label's account joint and move both partners' rows into it.

        Each row becomes the joint account's (`as_joint_row`), carrying a
        hand-set split into its owner shares.
        """
        async with uow:
            label = command.label
            if not any(a.name == label for a in await uow.accounts.get_all()):
                raise NotFoundError(f"No account named {label!r}")
            joint = Account(
                id=joint_account_id(label),
                name=label,
                kind="joint",
                owner_person_id=None,
            )
            persons = await uow.persons.get_all()
            personal_ids = [personal_account_id(p.id, label) for p in persons]
            rows, uploads = await load_rows_to_move(uow, personal_ids)
            await _assert_no_settlement_legs(uow, rows, label)

            moved = [
                as_joint_row(tx, account_id=joint.id, persons=persons, carry_split=True)
                for tx in rows
            ]
            kept, dropped = _collapse_twins(moved, uploads)
            await delete_transactions_with_links(uow, dropped)
            await uow.accounts.add_missing([joint])
            await uow.transactions.rekey_batch(kept)
            await uow.accounts.delete_by_ids(personal_ids)
            await uow.commit()
            return MarkAccountJointResult(
                account=joint, moved_count=len(kept), dropped_count=len(dropped)
            )
