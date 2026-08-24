from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class SettlementPortionModel(Base):
    """One month's slice of a settlement payment; slices sum to the amount."""

    __tablename__ = "settlement_portions"
    __table_args__: tuple[UniqueConstraint] = (
        UniqueConstraint(
            "settlement_id", "year", "month", name="uq_settlement_portion_period"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    settlement_id: Mapped[str] = mapped_column(
        String, ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[str] = mapped_column(String, nullable=False)
