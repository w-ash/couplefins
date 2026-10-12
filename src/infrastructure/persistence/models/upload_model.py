from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class UploadModel(Base):
    __tablename__ = "uploads"
    __table_args__: tuple[Index, ...] = (
        Index(
            "uq_uploads_content_sha256",
            "content_sha256",
            unique=True,
            postgresql_where=text("content_sha256 IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    person_id: Mapped[str] = mapped_column(
        String, ForeignKey("persons.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[str] = mapped_column(String, nullable=False)
    importer: Mapped[str] = mapped_column(
        String, nullable=False, server_default="monarch_csv"
    )
    content_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
