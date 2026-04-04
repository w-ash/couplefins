from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.person import Person
from src.domain.entities.reconciliation_period import ReconciliationPeriod
from src.domain.entities.settlement import Settlement
from src.domain.entities.settlement_merchant import SettlementMerchant
from src.domain.entities.settlement_transaction_link import SettlementTransactionLink
from src.domain.entities.transaction import Transaction
from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.entities.upload import Upload


def make_person(
    *,
    id: uuid.UUID | None = None,
    name: str = "Test Person",
    adjustment_account: str = "",
    password_hash: str = "",
    theme_preference: str = "system",
) -> Person:
    return Person(
        id=id or uuid.uuid4(),
        name=name,
        adjustment_account=adjustment_account,
        password_hash=password_hash,
        theme_preference=theme_preference,
    )


def make_transaction(
    *,
    id: uuid.UUID | None = None,
    upload_id: uuid.UUID | None = None,
    date: date = date(2026, 1, 15),
    merchant: str = "Test Merchant",
    category: str = "Dining Out",
    account: str = "Chase Sapphire",
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
) -> Transaction:
    return Transaction(
        id=id or uuid.uuid4(),
        upload_id=upload_id or uuid.uuid4(),
        date=date,
        merchant=merchant,
        category=category,
        account=account,
        original_statement=original_statement,
        occurrence=occurrence,
        notes=notes,
        amount=amount,
        tags=tags,
        payer_person_id=payer_person_id or uuid.uuid4(),
        payer_percentage=payer_percentage,
        household=household,
        is_settlement=is_settlement,
        is_excluded=is_excluded,
        original_date=original_date,
        original_amount=original_amount,
    )


def make_upload(
    *,
    id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    filename: str = "transactions.csv",
    uploaded_at: datetime | None = None,
) -> Upload:
    return Upload(
        id=id or uuid.uuid4(),
        person_id=person_id or uuid.uuid4(),
        filename=filename,
        uploaded_at=uploaded_at or datetime.now(UTC),
    )


def make_category_group(
    *,
    id: uuid.UUID | None = None,
    name: str = "Food & Dining",
    icon: str | None = None,
) -> CategoryGroup:
    return CategoryGroup(id=id or uuid.uuid4(), name=name, icon=icon)


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
) -> TransactionEdit:
    return TransactionEdit(
        id=id or uuid.uuid4(),
        transaction_id=transaction_id or uuid.uuid4(),
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        edited_at=edited_at or datetime.now(UTC),
    )


def make_settlement(
    *,
    id: uuid.UUID | None = None,
    year: int = 2026,
    month: int = 1,
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
        year=year,
        month=month,
        amount=amount,
        from_person_id=from_person_id or uuid.uuid4(),
        to_person_id=to_person_id or uuid.uuid4(),
        method=method,
        is_waived=is_waived,
        notes=notes,
        settled_at=settled_at or datetime.now(UTC),
        created_at=created_at or datetime.now(UTC),
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
