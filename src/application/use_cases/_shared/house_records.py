"""The home's loans and obligations, as the House use cases enter them.

A loan's terms are entered once (`LoanTerms`); an obligation's are entered
and edited freely (`ObligationTerms`). Both belong to the couple's asset,
which must exist first. The terms only normalize what was entered; the
entities check the values.
"""

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
import uuid

import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    as_validation_error,
    build_validated,
    quantize_cents,
)
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.co_owned_asset import CoOwnedAsset
from src.domain.entities.loan import Loan, LoanKind, slugify
from src.domain.entities.obligation import Obligation, ObligationKind
from src.domain.exceptions import ValidationError
from src.domain.loans import loan_tag
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

_RATE_EXP = Decimal("0.001")


def _quantize_rate(value: Decimal) -> Decimal:
    """attrs converter — an annual rate persists as a percent to 0.001."""
    return value.quantize(_RATE_EXP, rounding=ROUND_HALF_UP)


def _blank_as_none(value: str | None) -> str | None:
    """attrs converter — text without its outer spaces; None when blank."""
    stripped = (value or "").strip()
    return stripped or None


@define(frozen=True, slots=True)
class LoanTerms:
    """A new loan, as entered: every value of the loan but its identity,
    slug, and history (`Loan` checks them). ``annual_rate`` is a percent
    (6.5 for 6.5%); the statement balance and its date anchor the loan's
    balance."""

    name: str = field(converter=str.strip)
    lender: str = field(converter=str.strip)
    kind: LoanKind
    principal: Decimal = field(converter=quantize_cents)
    annual_rate: Decimal = field(converter=_quantize_rate)
    payment: Decimal = field(converter=quantize_cents)
    first_due_on: date
    statement_balance: Decimal = field(converter=quantize_cents)
    statement_balance_as_of: date
    term_months: int | None = None
    notes: str = ""


@define(frozen=True, slots=True)
class ObligationTerms:
    """An obligation, as entered: every value but its identity and the row
    that paid it (`Obligation` checks them). ``pays_from`` is a pot's or an
    account's name, None when blank."""

    kind: ObligationKind
    description: str = field(converter=str.strip)
    amount: Decimal = field(converter=quantize_cents)
    due_on: date
    is_estimate: bool = False
    late_after: date | None = None
    pays_from: str | None = field(default=None, converter=_blank_as_none)
    loan_id: uuid.UUID | None = None
    notes: str = ""


async def require_asset(uow: UnitOfWorkProtocol) -> CoOwnedAsset:
    """The couple's asset. Raise ValidationError before the home is set up."""
    asset = await uow.co_owned_assets.get_current()
    if asset is None:
        raise ValidationError("Set up the home in Settings → House first")
    return asset


async def add_loan(
    uow: UnitOfWorkProtocol, terms: LoanTerms, asset_id: uuid.UUID
) -> Loan:
    """Save a new open loan on the asset, with its slug from its name.

    Raise ValidationError when the loan rejects a term (a name with no
    letter or digit among them) or another loan has the same slug.
    """
    loan = build_validated(
        Loan,
        attrs.asdict(terms, recurse=False),
        id=uuid.uuid4(),
        asset_id=asset_id,
        slug=slugify(terms.name),
        replaced_by_loan_id=None,
        closed_on=None,
        created_at=datetime.now(UTC),
    )
    if await uow.loans.get_by_slug(loan.slug) is not None:
        raise ValidationError(
            f"A loan already uses the tag {loan_tag(loan)}; name this loan differently"
        )
    return await uow.loans.save(loan)


async def close_loan(
    uow: UnitOfWorkProtocol,
    loan: Loan,
    closed_on: date,
    replaced_by: uuid.UUID | None = None,
) -> Loan:
    """Close an open loan on `closed_on`, any date, replaced by
    `replaced_by` when given, and save it.

    A closed loan has no more payments, so its unpaid payment obligations
    due after `closed_on` are deleted; the others stay with its history.
    Raise ValidationError when the loan is closed already.
    """
    if not loan.is_open:
        raise ValidationError(f"Loan {loan.name!r} is already closed")
    closed = as_validation_error(
        attrs.evolve, loan, closed_on=closed_on, replaced_by_loan_id=replaced_by
    )
    stale = [
        o.id
        for o in await uow.obligations.get_by_loan_id(loan.id)
        if o.kind == "loan_payment" and not o.is_paid and o.due_on > closed_on
    ]
    await uow.obligations.delete_by_ids(stale)
    return await uow.loans.save(closed)


async def build_obligation(
    uow: UnitOfWorkProtocol,
    current: Obligation | None,
    asset_id: uuid.UUID,
    terms: ObligationTerms,
) -> Obligation:
    """The obligation the terms describe: `current` with every value but
    the row that paid it replaced, or a new unpaid obligation of the asset
    when `current` is None.

    Raise NotFoundError when its loan does not exist, and ValidationError
    when its loan is another asset's or the obligation rejects a value.
    """
    if terms.loan_id is not None:
        loan = await require_by_id(uow.loans.get_by_id, terms.loan_id, "Loan")
        if loan.asset_id != asset_id:
            raise ValidationError(f"Loan {loan.id} is not this home's")
    values = attrs.asdict(terms, recurse=False)
    if current is None:
        return build_validated(
            Obligation,
            values,
            id=uuid.uuid4(),
            asset_id=asset_id,
            paid_by_transaction_id=None,
        )
    return as_validation_error(attrs.evolve, current, **values)
