from uuid import UUID

from attrs import define, evolve

from src.application.use_cases._shared.transactions import load_rows_to_move
from src.domain.constants import SplitDefaults
from src.domain.entities.account import Account, joint_account_id, personal_account_id
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UnmarkAccountJointCommand:
    label: str


@define(frozen=True, slots=True)
class UnmarkAccountJointResult:
    moved_count: int


def _in_personal_account(tx: Transaction, uploader: UUID) -> Transaction:
    """The row as its uploader's: paid by them, household, unsplit unless
    its owner shares carry a split back to the uploader's percentage."""
    return evolve(
        tx,
        account_id=personal_account_id(uploader, tx.account),
        payer_person_id=uploader,
        payer_percentage=(
            tx.owner_shares[uploader]
            if tx.owner_shares is not None
            else SplitDefaults.MAX_PAYER_PERCENTAGE
        ),
        household=True,
        owner_shares=None,
        depositor_person_id=None,
    )


@define(slots=True)
class UnmarkAccountJointUseCase:
    async def execute(
        self, command: UnmarkAccountJointCommand, uow: UnitOfWorkProtocol
    ) -> UnmarkAccountJointResult:
        """Return a joint account's rows to the partners who imported them."""
        async with uow:
            joint_id = joint_account_id(command.label)
            if not await uow.accounts.get_by_ids([joint_id]):
                raise NotFoundError(f"No joint account named {command.label!r}")
            rows, uploads = await load_rows_to_move(uow, [joint_id])
            uploaders = {upload.person_id for upload in uploads.values()}
            await uow.accounts.add_missing([
                Account(
                    id=personal_account_id(pid, command.label),
                    name=command.label,
                    kind="personal",
                    owner_person_id=pid,
                )
                for pid in sorted(uploaders, key=str)
            ])
            await uow.transactions.rekey_batch([
                _in_personal_account(tx, uploads[tx.upload_id].person_id) for tx in rows
            ])
            await uow.accounts.delete_by_ids([joint_id])
            await uow.commit()
            return UnmarkAccountJointResult(moved_count=len(rows))
