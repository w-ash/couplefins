from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.person import Person
from src.domain.entities.reconciliation_period import ReconciliationPeriod
from src.domain.entities.transaction import Transaction
from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.entities.upload import Upload


def make_person(
    *,
    id: uuid.UUID | None = None,
    name: str = "Test Person",
    adjustment_account: str = "",
) -> Person:
    return Person(
        id=id or uuid.uuid4(), name=name, adjustment_account=adjustment_account
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
    payer_percentage: int | None = 50,
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
) -> CategoryGroup:
    return CategoryGroup(id=id or uuid.uuid4(), name=name)


_MISSING = object()


def make_category_mapping(
    *,
    category: str = "Dining Out",
    group_id: uuid.UUID | object | None = _MISSING,
) -> CategoryMapping:
    return CategoryMapping(
        category=category,
        group_id=uuid.uuid4() if group_id is _MISSING else group_id,  # type: ignore[arg-type]
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
    effective_from: date = date(2026, 1, 1),
) -> CategoryGroupBudget:
    return CategoryGroupBudget(
        id=id or uuid.uuid4(),
        group_id=group_id or uuid.uuid4(),
        monthly_amount=monthly_amount,
        effective_from=effective_from,
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
