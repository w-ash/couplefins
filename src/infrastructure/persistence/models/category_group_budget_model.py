from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class CategoryGroupBudgetModel(Base):
    __tablename__ = "category_group_budgets"
    __table_args__ = (UniqueConstraint("group_id", "effective_from"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    group_id: Mapped[str] = mapped_column(
        String, ForeignKey("category_groups.id"), nullable=False
    )
    monthly_amount: Mapped[str] = mapped_column(String, nullable=False)
    effective_from: Mapped[str] = mapped_column(String, nullable=False)
