from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class SettlementTransactionLinkModel(Base):
    __tablename__ = "settlement_transaction_links"
    __table_args__ = (
        Index("ix_stl_settlement_id", "settlement_id"),
        Index("ix_stl_transaction_id", "transaction_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    settlement_id: Mapped[str] = mapped_column(
        String, ForeignKey("settlements.id"), nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(
        String, ForeignKey("transactions.id"), nullable=False
    )
