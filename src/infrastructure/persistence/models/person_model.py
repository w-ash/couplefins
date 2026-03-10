from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class PersonModel(Base):
    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    adjustment_account: Mapped[str] = mapped_column(
        String, nullable=False, server_default=""
    )
