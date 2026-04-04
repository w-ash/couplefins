from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class CategoryGroupBudgetModel(Base):
    __tablename__ = "category_group_budgets"
    __table_args__ = (
        Index(
            "uq_budget_group_month_personal",
            "group_id",
            "year",
            "month",
            "person_id",
            unique=True,
            postgresql_where=text("person_id IS NOT NULL"),
        ),
        Index(
            "uq_budget_group_month_household",
            "group_id",
            "year",
            "month",
            unique=True,
            postgresql_where=text("person_id IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    group_id: Mapped[str] = mapped_column(
        String, ForeignKey("category_groups.id"), nullable=False
    )
    monthly_amount: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    person_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("persons.id"), nullable=True, default=None
    )
