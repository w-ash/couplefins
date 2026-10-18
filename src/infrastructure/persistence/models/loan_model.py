from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.loan import LOAN_KINDS
from src.infrastructure.persistence.models.base import Base

_KINDS = ", ".join(f"'{kind}'" for kind in LOAN_KINDS)


class LoanModel(Base):
    """A loan on the co-owned home. Its terms are never updated: a refinance
    adds the replacing loan and closes this one."""

    __tablename__ = "loans"
    __table_args__: tuple[CheckConstraint] = (
        CheckConstraint(f"kind IN ({_KINDS})", name="ck_loans_kind"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    asset_id: Mapped[str] = mapped_column(
        String, ForeignKey("co_owned_assets.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    lender: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    principal: Mapped[str] = mapped_column(String, nullable=False)
    annual_rate: Mapped[str] = mapped_column(String, nullable=False)
    payment: Mapped[str] = mapped_column(String, nullable=False)
    term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_due_on: Mapped[str] = mapped_column(String, nullable=False)
    statement_balance: Mapped[str] = mapped_column(String, nullable=False)
    statement_balance_as_of: Mapped[str] = mapped_column(String, nullable=False)
    replaced_by_loan_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("loans.id"), nullable=True
    )
    closed_on: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
