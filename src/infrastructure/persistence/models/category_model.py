from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    group_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("category_groups.id"), nullable=True
    )
    include_personal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )
