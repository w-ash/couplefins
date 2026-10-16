from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__: tuple[UniqueConstraint | CheckConstraint | Index, ...] = (
        UniqueConstraint(
            "date",
            "amount",
            "account_id",
            "original_statement",
            "occurrence",
            name="uq_transactions_natural_key",
        ),
        CheckConstraint(
            "owner_shares IS NULL OR payer_person_id IS NULL",
            name="ck_transactions_owner_shares_joint_only",
        ),
        CheckConstraint(
            "depositor_person_id IS NULL OR payer_person_id IS NULL",
            name="ck_transactions_depositor_joint_only",
        ),
        Index("ix_transactions_household_date", "household", "date"),
        Index("ix_transactions_upload_id", "upload_id"),
        Index("ix_transactions_account_id", "account_id"),
        Index("ix_transactions_person_date", "payer_person_id", "date"),
        Index("ix_transactions_tags_gin", "tags", postgresql_using="gin"),
        Index(
            "ix_transactions_non_settlement_date",
            "household",
            "date",
            postgresql_where=text("NOT is_settlement"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    upload_id: Mapped[str] = mapped_column(
        String, ForeignKey("uploads.id"), nullable=False
    )
    date: Mapped[str] = mapped_column(String, nullable=False)
    merchant: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    account: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), nullable=False
    )
    original_statement: Mapped[str] = mapped_column(String, nullable=False)
    occurrence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    household: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # NULL on a joint account's row.
    payer_person_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("persons.id"), nullable=True
    )
    payer_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_settlement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_date: Mapped[str | None] = mapped_column(String, nullable=True)
    original_amount: Mapped[str | None] = mapped_column(String, nullable=True)
    depositor_person_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("persons.id", name="fk_transactions_depositor_person"),
        nullable=True,
    )
    # none_as_null: Python None stores SQL NULL, not JSON null, as the
    # joint-only check constraint requires.
    owner_shares: Mapped[dict[str, int] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
