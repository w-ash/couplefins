from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class TransactionEditModel(Base):
    __tablename__ = "transaction_edits"
    __table_args__ = (Index("ix_transaction_edits_transaction_id", "transaction_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(
        String, ForeignKey("transactions.id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[str] = mapped_column(String, nullable=False)
    new_value: Mapped[str] = mapped_column(String, nullable=False)
    edited_at: Mapped[str] = mapped_column(String, nullable=False)
