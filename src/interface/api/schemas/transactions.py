import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.application.use_cases.bulk_modify_tags import TagAction
from src.domain.constants import SplitDefaults


def _validate_payer_pct(v: int | None) -> int | None:
    if v is not None and not (0 <= v <= SplitDefaults.MAX_PAYER_PERCENTAGE):
        raise ValueError(
            f"payer_percentage must be 0-{SplitDefaults.MAX_PAYER_PERCENTAGE}"
        )
    return v


def _validate_ids_non_empty(v: list[UUID]) -> list[UUID]:
    if not v:
        raise ValueError("At least one transaction ID is required")
    return v


class SplitEntryRequest(BaseModel):
    transaction_id: UUID
    payer_percentage: int

    @field_validator("payer_percentage")
    @classmethod
    def validate_range(cls, v: int) -> int:
        if not (0 <= v <= SplitDefaults.MAX_PAYER_PERCENTAGE):
            raise ValueError(
                f"payer_percentage must be 0-{SplitDefaults.MAX_PAYER_PERCENTAGE}"
            )
        return v


class UpdateSplitsRequest(BaseModel):
    splits: list[SplitEntryRequest]

    @field_validator("splits")
    @classmethod
    def validate_non_empty(cls, v: list[SplitEntryRequest]) -> list[SplitEntryRequest]:
        if not v:
            raise ValueError("At least one split entry is required")
        return v


class UpdateSplitsResponse(BaseModel):
    updated_count: int


class UpdateTransactionRequest(BaseModel):
    date: datetime.date | None = None
    amount: float | None = None
    category: str | None = None
    tags: list[str] | None = None
    payer_percentage: int | None = None

    @field_validator("payer_percentage")
    @classmethod
    def validate_payer_percentage(cls, v: int | None) -> int | None:
        return _validate_payer_pct(v)


class TransactionEditResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    transaction_id: UUID
    field_name: str
    old_value: str
    new_value: str
    edited_at: datetime.datetime


class TransactionEditHistoryResponse(BaseModel):
    edits: list[TransactionEditResponse]


class UpdateTransactionResponse(BaseModel):
    id: UUID
    edits: list[TransactionEditResponse]


class BulkUpdateRequest(BaseModel):
    transaction_ids: list[UUID]
    category: str | None = None
    payer_percentage: int | None = None

    @field_validator("transaction_ids")
    @classmethod
    def validate_non_empty(cls, v: list[UUID]) -> list[UUID]:
        return _validate_ids_non_empty(v)

    @field_validator("payer_percentage")
    @classmethod
    def validate_payer_percentage(cls, v: int | None) -> int | None:
        return _validate_payer_pct(v)


class BulkUpdateResponse(BaseModel):
    updated_count: int


class BulkModifyTagsRequest(BaseModel):
    transaction_ids: list[UUID]
    action: TagAction
    tags: list[str]

    @field_validator("transaction_ids")
    @classmethod
    def validate_ids_non_empty(cls, v: list[UUID]) -> list[UUID]:
        return _validate_ids_non_empty(v)

    @field_validator("tags")
    @classmethod
    def validate_tags_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one tag is required")
        return v


class BulkModifyTagsResponse(BaseModel):
    updated_count: int
