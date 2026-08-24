from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class SettlementModel(Base):
    """A payment between the couple. What it covers lives in the
    settlement_transaction_links / settlement_portions tables."""

    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    amount: Mapped[str] = mapped_column(String, nullable=False)
    from_person_id: Mapped[str] = mapped_column(
        String, ForeignKey("persons.id"), nullable=False
    )
    to_person_id: Mapped[str] = mapped_column(
        String, ForeignKey("persons.id"), nullable=False
    )
    method: Mapped[str | None] = mapped_column(String, nullable=True)
    is_waived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str] = mapped_column(String, nullable=False, default="")
    settled_at: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
