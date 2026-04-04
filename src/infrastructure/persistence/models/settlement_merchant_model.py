from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class SettlementMerchantModel(Base):
    __tablename__ = "settlement_merchants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    merchant_pattern: Mapped[str] = mapped_column(String, nullable=False)
