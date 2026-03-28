from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class SettlementModel(Base):
    __tablename__ = "settlements"
    __table_args__: tuple[UniqueConstraint | Index, ...] = (
        UniqueConstraint(
            "year",
            "month",
            "from_person_id",
            "settled_at",
            name="uq_settlements_period_person_time",
        ),
        Index("ix_settlements_year_month", "year", "month"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
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
