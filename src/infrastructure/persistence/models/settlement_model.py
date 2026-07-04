from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class SettlementModel(Base):
    __tablename__ = "settlements"
    __table_args__: tuple[Index, ...] = (
        Index("ix_settlements_year_month", "year", "month"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # Optional "recorded against" annotations since v1.7.5 — display metadata,
    # never ledger math. Entity typing flips to `int | None` in handoff 2.
    year: Mapped[int] = mapped_column(Integer, nullable=True)
    month: Mapped[int] = mapped_column(Integer, nullable=True)
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
