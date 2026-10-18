from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class CoOwnedAssetModel(Base):
    """The couple's home and the settings of their shares in it. One row."""

    __tablename__ = "co_owned_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    repair_threshold: Mapped[str] = mapped_column(String, nullable=False)
    qualifying_kinds: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    bank_balance: Mapped[str | None] = mapped_column(String, nullable=True)
    bank_balance_as_of: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
