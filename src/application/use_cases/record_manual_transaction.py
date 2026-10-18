from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    as_validation_error,
    non_empty,
    positive_decimal,
    quantize_cents,
)
from src.application.use_cases._shared.finalization import (
    assert_period_not_finalized,
)
from src.application.use_cases._shared.transaction_reads import fetch_listed_rows
from src.application.use_cases._shared.transactions import manual_accounts
from src.domain.constants import (
    HOUSE_CONTRIBUTION_CATEGORY,
    SHARE_TAG_PREFIX,
    SplitDefaults,
)
from src.domain.entities.account import Account, joint_account_id, personal_account_id
from src.domain.entities.category import Category
from src.domain.entities.co_owned_asset import ContributionKind
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import MANUAL_IMPORTER, Upload, manual_upload_id
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.split_rules import check_owner_shares


@define(frozen=True, slots=True)
class RecordManualTransactionCommand:
    """A contribution that passed through no imported account.

    ``amount`` is what was paid (> 0); the row stores it as money out.
    ``owner_shares`` gives each owner's percentage of it.
    """

    account_name: str = field(validator=non_empty)
    date: date
    amount: Decimal = field(converter=quantize_cents, validator=positive_decimal)
    description: str = field(validator=non_empty)
    share_kind: ContributionKind
    owner_shares: Mapping[uuid.UUID, int]
    entered_by_person_id: uuid.UUID
    document_ref: str = ""


@define(frozen=True, slots=True)
class RecordManualTransactionResult:
    transaction: Transaction


async def _next_occurrence(
    uow: UnitOfWorkProtocol, account: Account, key: tuple[date, Decimal, str]
) -> int:
    """An occurrence that no row of the account with the same (date, amount,
    statement) holds, so the natural key never collides. Reads the rows
    dated that day now, so a row edited onto that date still counts."""
    day = key[0]
    rows = await fetch_listed_rows(uow, (day, day))
    same = [
        tx.occurrence
        for tx in rows
        if tx.account_id == account.id
        and (tx.date, tx.amount, tx.original_statement) == key
    ]
    return max(same, default=-1) + 1


async def _manual_account(
    uow: UnitOfWorkProtocol,
    command: RecordManualTransactionCommand,
    couple: Sequence[uuid.UUID],
) -> Account:
    """The hand-entered joint account the row goes in. On first use, add it
    and its manual upload, saved by the person who enters the row.

    Raise ValidationError when the account name is an imported account's
    label, personal or joint: hand-entered rows keep an account of their own.
    """
    name = command.account_name
    account_id = joint_account_id(name)
    found = await uow.accounts.get_by_ids([
        account_id,
        *(personal_account_id(person, name) for person in couple),
    ])
    if found:
        if await manual_accounts(uow, found) != found:
            raise ValidationError(
                f"{name!r} is an imported account; "
                "name the account of hand-entered rows differently"
            )
        return found[0]
    account = Account(id=account_id, name=name, kind="joint", owner_person_id=None)
    await uow.accounts.add_missing([account])
    await uow.uploads.save(
        Upload(
            id=manual_upload_id(account.id),
            person_id=command.entered_by_person_id,
            filename=f"{name} (entered by hand)",
            uploaded_at=datetime.now(UTC),
            importer=MANUAL_IMPORTER,
            content_sha256=None,
        )
    )
    return account


async def _ensure_category(uow: UnitOfWorkProtocol) -> None:
    """Add the hand-entered rows' category when it is missing. It maps to the
    transfer-kind group (the first by name) when one exists, as money moved
    into the home is no spending; else it stays unmapped."""
    if await uow.categories.get_by_name(HOUSE_CONTRIBUTION_CATEGORY) is not None:
        return
    transfer = min(
        (g for g in await uow.category_groups.get_all() if g.kind == "transfer"),
        key=lambda g: g.name,
        default=None,
    )
    await uow.categories.save(
        Category(
            id=uuid.uuid4(),
            name=HOUSE_CONTRIBUTION_CATEGORY,
            group_id=transfer.id if transfer else None,
        )
    )


@define(slots=True)
class RecordManualTransactionUseCase:
    async def execute(
        self, command: RecordManualTransactionCommand, uow: UnitOfWorkProtocol
    ) -> RecordManualTransactionResult:
        """Record a contribution as a row of a hand-entered joint account.

        The row has no payer and is split by the owner shares. It is
        excluded, so it counts in no spending lens and never in settlement;
        its `share:<kind>` tag credits the owners' capital. The account, its
        manual upload, and the row's category are added on first use. Raise
        ValidationError when the owner shares do not name the couple or the
        account name is an imported account's label, and PeriodFinalizedError
        when the row's month is finalized.
        """
        async with uow:
            couple = [p.id for p in await uow.persons.get_all()]
            as_validation_error(check_owner_shares, command.owner_shares, couple)
            await assert_period_not_finalized(
                uow, command.date.year, command.date.month
            )
            account = await _manual_account(uow, command, couple)
            await _ensure_category(uow)
            amount = -command.amount
            key = (command.date, amount, command.description)
            row = Transaction(
                id=uuid.uuid4(),
                upload_id=manual_upload_id(account.id),
                date=command.date,
                merchant=command.description,
                category=HOUSE_CONTRIBUTION_CATEGORY,
                account=account.name,
                account_id=account.id,
                original_statement=command.description,
                occurrence=await _next_occurrence(uow, account, key),
                notes=command.document_ref,
                amount=amount,
                tags=(f"{SHARE_TAG_PREFIX}{command.share_kind}",),
                payer_person_id=None,
                payer_percentage=SplitDefaults.MAX_PAYER_PERCENTAGE,
                household=False,
                is_excluded=True,
                owner_shares=command.owner_shares,
            )
            await uow.transactions.save_batch([row])
            await uow.commit()
            return RecordManualTransactionResult(transaction=row)
