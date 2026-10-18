from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.obligation import OBLIGATION_KINDS
from src.infrastructure.persistence.models.base import Base

_KINDS = ", ".join(f"'{kind}'" for kind in OBLIGATION_KINDS)


class ObligationModel(Base):
    """A payment due on the co-owned home. Deleting the row that paid it
    leaves it unpaid."""

    __tablename__ = "obligations"
    __table_args__: tuple[CheckConstraint | Index, ...] = (
        CheckConstraint(f"kind IN ({_KINDS})", name="ck_obligations_kind"),
        Index("ix_obligations_asset_due", "asset_id", "due_on"),
        Index("ix_obligations_loan_id", "loan_id"),
        Index("ix_obligations_paid_by_transaction_id", "paid_by_transaction_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    asset_id: Mapped[str] = mapped_column(
        String, ForeignKey("co_owned_assets.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[str] = mapped_column(String, nullable=False)
    is_estimate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    due_on: Mapped[str] = mapped_column(String, nullable=False)
    late_after: Mapped[str | None] = mapped_column(String, nullable=True)
    pays_from: Mapped[str | None] = mapped_column(String, nullable=True)
    loan_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("loans.id"), nullable=True
    )
    paid_by_transaction_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str] = mapped_column(String, nullable=False, server_default="")
