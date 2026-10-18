from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

import attrs

from src.domain.constants import DEFAULT_MANUAL_ACCOUNT, HOUSE_CONTRIBUTION_CATEGORY
from src.domain.entities.account import (
    Account,
    AccountKind,
    joint_account_id,
    personal_account_id,
)
from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup, GroupKind
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.co_owned_asset import (
    CONTRIBUTION_KINDS,
    ContributionKind,
    CoOwnedAsset,
)
from src.domain.entities.loan import Loan, LoanKind, slugify
from src.domain.entities.obligation import Obligation, ObligationKind, ObligationStatus
from src.domain.entities.person import Person
from src.domain.entities.reconciliation_period import ReconciliationPeriod
from src.domain.entities.settlement import Settlement
from src.domain.entities.settlement_merchant import SettlementMerchant
from src.domain.entities.settlement_portion import SettlementPortion
from src.domain.entities.settlement_transaction_link import SettlementTransactionLink
from src.domain.entities.transaction import Transaction
from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.entities.upload import Upload
from src.domain.house import (
    ObligationFigures,
    OwnerAmount,
    OwnerShare,
    ShareHistoryPoint,
)


def make_person(
    *,
    id: uuid.UUID | None = None,
    name: str = "Test Person",
    adjustment_account: str = "",
    password_hash: str = "",
    theme_preference: str = "system",
    chat_voice: str = "fiona",
) -> Person:
    return Person(
        id=id or uuid.uuid4(),
        name=name,
        adjustment_account=adjustment_account,
        password_hash=password_hash,
        theme_preference=theme_preference,
        chat_voice=chat_voice,
    )


# The canonical test couple with fixed IDs, shared across suites. Person is
# frozen, so module-level sharing is safe.
ALICE = make_person(name="Alice", id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
BOB = make_person(name="Bob", id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
# The couple's ids, in the order a split takes them.
COUPLE_IDS = (ALICE.id, BOB.id)


def make_transaction(
    *,
    id: uuid.UUID | None = None,
    upload_id: uuid.UUID | None = None,
    date: date = date(2026, 1, 15),
    merchant: str = "Test Merchant",
    category: str = "Dining Out",
    account: str = "Chase Sapphire",
    account_id: uuid.UUID | None = None,
    original_statement: str = "TEST MERCHANT",
    occurrence: int = 0,
    notes: str = "",
    amount: Decimal = Decimal("-50.00"),
    tags: tuple[str, ...] = ("shared",),
    payer_person_id: uuid.UUID | None = None,
    payer_percentage: int = 50,
    household: bool = True,
    is_settlement: bool = False,
    is_excluded: bool = False,
    original_date: date | None = None,
    original_amount: Decimal | None = None,
    joint: bool = False,
    owner_shares: Mapping[uuid.UUID, int] | None = None,
    depositor_person_id: uuid.UUID | None = None,
) -> Transaction:
    """A transaction; a random payer when none is given. `joint` makes it a
    joint account's row: no payer, the joint account of `account`, household,
    unsplit (the import defaults; `payer_person_id`, `payer_percentage` and
    `household` are ignored)."""
    if joint:
        payer = None
        default_account_id = joint_account_id(account)
        payer_percentage, household = 100, True
    else:
        payer = payer_person_id or uuid.uuid4()
        default_account_id = personal_account_id(payer, account)
    return Transaction(
        id=id or uuid.uuid4(),
        upload_id=upload_id or uuid.uuid4(),
        date=date,
        merchant=merchant,
        category=category,
        account=account,
        account_id=account_id or default_account_id,
        original_statement=original_statement,
        occurrence=occurrence,
        notes=notes,
        amount=amount,
        tags=tags,
        payer_person_id=payer,
        payer_percentage=payer_percentage,
        household=household,
        is_settlement=is_settlement,
        is_excluded=is_excluded,
        original_date=original_date,
        original_amount=original_amount,
        depositor_person_id=depositor_person_id,
        owner_shares=owner_shares,
    )


def make_share_transaction(
    kind: str,
    amount: Decimal = Decimal("-100.00"),
    *,
    date: date = date(2026, 1, 15),
    payer_person_id: uuid.UUID | None = None,
    payer_percentage: int = 50,
    joint: bool = False,
    owner_shares: Mapping[uuid.UUID, int] | None = None,
    tags: tuple[str, ...] = (),
) -> Transaction:
    """A row tagged `share:<kind>` after `tags`, paid by Alice unless another
    payer is given or the row is `joint`."""
    return make_transaction(
        date=date,
        amount=amount,
        tags=(*tags, f"share:{kind}"),
        payer_person_id=payer_person_id or ALICE.id,
        payer_percentage=payer_percentage,
        joint=joint,
        owner_shares=owner_shares,
    )


def make_manual_transaction(
    kind: ContributionKind = "closing",
    amount: Decimal = Decimal("-1000.00"),
    *,
    owner_shares: Mapping[uuid.UUID, int] | None = None,
    account: str = DEFAULT_MANUAL_ACCOUNT,
) -> Transaction:
    """A hand-entered contribution as recorded: a joint row, unsplit, not
    household, excluded, tagged with its kind."""
    row = make_transaction(
        joint=True,
        account=account,
        category=HOUSE_CONTRIBUTION_CATEGORY,
        amount=amount,
        tags=(f"share:{kind}",),
        owner_shares=owner_shares or {ALICE.id: 60, BOB.id: 40},
        is_excluded=True,
    )
    return attrs.evolve(row, household=False)


def make_co_owned_asset(
    *,
    id: uuid.UUID | None = None,
    name: str = "Home",
    repair_threshold: Decimal = Decimal("500.00"),
    qualifying_kinds: frozenset[ContributionKind] = frozenset(CONTRIBUTION_KINDS),
    bank_balance: Decimal | None = None,
    bank_balance_as_of: date | None = None,
    created_at: datetime | None = None,
) -> CoOwnedAsset:
    """An asset that counts every contribution kind by default."""
    return CoOwnedAsset(
        id=id or uuid.uuid4(),
        name=name,
        repair_threshold=repair_threshold,
        qualifying_kinds=qualifying_kinds,
        bank_balance=bank_balance,
        bank_balance_as_of=bank_balance_as_of,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


def make_upload(
    *,
    id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    filename: str = "transactions.csv",
    uploaded_at: datetime | None = None,
    importer: str = "monarch_csv",
    content_sha256: str | None = None,
) -> Upload:
    return Upload(
        id=id or uuid.uuid4(),
        person_id=person_id or uuid.uuid4(),
        filename=filename,
        uploaded_at=uploaded_at or datetime.now(UTC),
        importer=importer,
        content_sha256=content_sha256,
    )


def make_account(
    *,
    id: uuid.UUID | None = None,
    name: str = "Chase Sapphire",
    kind: AccountKind = "personal",
    owner_person_id: uuid.UUID | None = None,
) -> Account:
    return Account(
        id=id or uuid.uuid4(),
        name=name,
        kind=kind,
        owner_person_id=(
            owner_person_id or uuid.uuid4() if kind == "personal" else None
        ),
    )


def make_joint_account(name: str = "Joint Checking") -> Account:
    """The joint account a joint row of label `name` belongs to."""
    return Account(
        id=joint_account_id(name), name=name, kind="joint", owner_person_id=None
    )


def make_category_group(
    *,
    id: uuid.UUID | None = None,
    name: str = "Food & Dining",
    icon: str | None = None,
    kind: GroupKind = "expense",
) -> CategoryGroup:
    return CategoryGroup(id=id or uuid.uuid4(), name=name, icon=icon, kind=kind)


_MISSING_GROUP = object()


def make_category(
    *,
    id: uuid.UUID | None = None,
    name: str = "Dining Out",
    group_id: uuid.UUID | object | None = _MISSING_GROUP,
    include_personal: bool = False,
) -> Category:
    return Category(
        id=id or uuid.uuid4(),
        name=name,
        group_id=uuid.uuid4() if group_id is _MISSING_GROUP else group_id,  # type: ignore[arg-type]
        include_personal=include_personal,
    )


def make_reconciliation_period(
    *,
    id: uuid.UUID | None = None,
    year: int = 2026,
    month: int = 1,
    is_finalized: bool = False,
    finalized_at: datetime | None = None,
    notes: str = "",
    created_at: datetime | None = None,
) -> ReconciliationPeriod:
    return ReconciliationPeriod(
        id=id or uuid.uuid4(),
        year=year,
        month=month,
        is_finalized=is_finalized,
        finalized_at=finalized_at,
        notes=notes,
        created_at=created_at or datetime.now(UTC),
    )


def make_transfer_group() -> tuple[CategoryGroup, Category]:
    """The seeded Transfer group with its Credit Card Payment category."""
    group = make_category_group(name="Transfer", kind="transfer")
    return group, make_category(name="Credit Card Payment", group_id=group.id)


def make_income_group() -> tuple[CategoryGroup, Category]:
    """The seeded Income group with its Paychecks category."""
    group = make_category_group(name="Income", kind="income")
    return group, make_category(name="Paychecks", group_id=group.id)


def make_category_group_budget(
    *,
    id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    monthly_amount: Decimal = Decimal("500.00"),
    year: int = 2026,
    month: int = 1,
    person_id: uuid.UUID | None = None,
) -> CategoryGroupBudget:
    return CategoryGroupBudget(
        id=id or uuid.uuid4(),
        group_id=group_id or uuid.uuid4(),
        monthly_amount=monthly_amount,
        year=year,
        month=month,
        person_id=person_id,
    )


def make_transaction_edit(
    *,
    id: uuid.UUID | None = None,
    transaction_id: uuid.UUID | None = None,
    field_name: str = "category",
    old_value: str = "Dining Out",
    new_value: str = "Fast Food",
    edited_at: datetime | None = None,
    edited_by_person_id: uuid.UUID | None = None,
) -> TransactionEdit:
    return TransactionEdit(
        id=id or uuid.uuid4(),
        transaction_id=transaction_id or uuid.uuid4(),
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        edited_at=edited_at or datetime.now(UTC),
        edited_by_person_id=edited_by_person_id,
    )


def make_settlement(
    *,
    id: uuid.UUID | None = None,
    amount: Decimal = Decimal("50.00"),
    from_person_id: uuid.UUID | None = None,
    to_person_id: uuid.UUID | None = None,
    method: str | None = "Venmo",
    is_waived: bool = False,
    notes: str = "",
    settled_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Settlement:
    return Settlement(
        id=id or uuid.uuid4(),
        amount=amount,
        from_person_id=from_person_id or uuid.uuid4(),
        to_person_id=to_person_id or uuid.uuid4(),
        method=method,
        is_waived=is_waived,
        notes=notes,
        settled_at=settled_at or datetime.now(UTC),
        created_at=created_at or datetime.now(UTC),
    )


def make_settlement_portion(
    *,
    id: uuid.UUID | None = None,
    settlement_id: uuid.UUID | None = None,
    year: int = 2026,
    month: int = 1,
    amount: Decimal = Decimal("50.00"),
) -> SettlementPortion:
    return SettlementPortion(
        id=id or uuid.uuid4(),
        settlement_id=settlement_id or uuid.uuid4(),
        year=year,
        month=month,
        amount=amount,
    )


def make_settlement_transaction_link(
    *,
    id: uuid.UUID | None = None,
    settlement_id: uuid.UUID | None = None,
    transaction_id: uuid.UUID | None = None,
) -> SettlementTransactionLink:
    return SettlementTransactionLink(
        id=id or uuid.uuid4(),
        settlement_id=settlement_id or uuid.uuid4(),
        transaction_id=transaction_id or uuid.uuid4(),
    )


def make_settlement_merchant(
    *,
    id: uuid.UUID | None = None,
    name: str = "Venmo",
    merchant_pattern: str = "venmo",
) -> SettlementMerchant:
    return SettlementMerchant(
        id=id or uuid.uuid4(),
        name=name,
        merchant_pattern=merchant_pattern,
    )


def make_owner_amount(
    *,
    person_id: uuid.UUID | None = None,
    amount: Decimal = Decimal("100.00"),
) -> OwnerAmount:
    return OwnerAmount(person_id=person_id or uuid.uuid4(), amount=amount)


def make_owner_share(
    *,
    person_id: uuid.UUID | None = None,
    capital: Decimal = Decimal("100.00"),
    percent: Decimal = Decimal(50),
) -> OwnerShare:
    return OwnerShare(
        person_id=person_id or uuid.uuid4(), capital=capital, percent=percent
    )


def make_share_history_point(
    *,
    year: int = 2026,
    month: int = 1,
    owners: tuple[OwnerShare, ...] = (),
) -> ShareHistoryPoint:
    return ShareHistoryPoint(year=year, month=month, owners=owners)


def make_obligation_figures(
    *,
    id: uuid.UUID | None = None,
    name: str = "Mortgage payment",
    kind: ObligationKind = "property_tax",
    status: ObligationStatus = "due",
    amount: Decimal = Decimal("100.00"),
    is_estimate: bool = False,
    due: date = date(2026, 11, 1),
    late_after: date | None = None,
    pays_from: str | None = "Loan payments",
    shortfall: Decimal | None = None,
) -> ObligationFigures:
    return ObligationFigures(
        id=id or uuid.uuid4(),
        name=name,
        kind=kind,
        status=status,
        amount=amount,
        is_estimate=is_estimate,
        due=due,
        late_after=late_after,
        pays_from=pays_from,
        loan_id=None,
        paid_by_transaction_id=None,
        shortfall=shortfall,
    )


def make_loan(
    *,
    id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    name: str = "Mortgage",
    slug: str | None = None,
    lender: str = "Example Bank",
    kind: LoanKind = "amortizing",
    principal: Decimal = Decimal("300000.00"),
    annual_rate: Decimal = Decimal("6.000"),
    payment: Decimal = Decimal("1798.65"),
    term_months: int | None = 360,
    first_due_on: date = date(2026, 2, 1),
    statement_balance: Decimal = Decimal("300000.00"),
    statement_balance_as_of: date = date(2026, 1, 1),
    replaced_by_loan_id: uuid.UUID | None = None,
    closed_on: date | None = None,
    notes: str = "",
    created_at: datetime | None = None,
) -> Loan:
    """An open loan; its slug is its name's (`slugify`) unless given."""
    return Loan(
        id=id or uuid.uuid4(),
        asset_id=asset_id or uuid.uuid4(),
        name=name,
        slug=slug or slugify(name),
        lender=lender,
        kind=kind,
        principal=principal,
        annual_rate=annual_rate,
        payment=payment,
        term_months=term_months,
        first_due_on=first_due_on,
        statement_balance=statement_balance,
        statement_balance_as_of=statement_balance_as_of,
        replaced_by_loan_id=replaced_by_loan_id,
        closed_on=closed_on,
        notes=notes,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


def make_obligation(
    *,
    id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    kind: ObligationKind = "property_tax",
    description: str = "Property tax, first installment",
    amount: Decimal = Decimal("1200.00"),
    is_estimate: bool = False,
    due_on: date = date(2026, 11, 1),
    late_after: date | None = None,
    pays_from: str | None = None,
    loan_id: uuid.UUID | None = None,
    paid_by_transaction_id: uuid.UUID | None = None,
    notes: str = "",
) -> Obligation:
    """An unpaid obligation; a `loan_payment` needs `loan_id`."""
    return Obligation(
        id=id or uuid.uuid4(),
        asset_id=asset_id or uuid.uuid4(),
        kind=kind,
        description=description,
        amount=amount,
        is_estimate=is_estimate,
        due_on=due_on,
        late_after=late_after,
        pays_from=pays_from,
        loan_id=loan_id,
        paid_by_transaction_id=paid_by_transaction_id,
        notes=notes,
    )
