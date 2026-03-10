from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_shared_date", "is_shared", "date"),
        Index("ix_transactions_upload_id", "upload_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    upload_id: Mapped[str] = mapped_column(
        String, ForeignKey("uploads.id"), nullable=False
    )
    date: Mapped[str] = mapped_column(String, nullable=False)
    merchant: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    account: Mapped[str] = mapped_column(String, nullable=False)
    original_statement: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[str] = mapped_column(String, nullable=False)
    tags_json: Mapped[str] = mapped_column(String, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payer_person_id: Mapped[str] = mapped_column(
        String, ForeignKey("persons.id"), nullable=False
    )
    payer_percentage: Mapped[int | None] = mapped_column(Integer, nullable=True)
