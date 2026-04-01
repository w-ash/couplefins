import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.application.use_cases.bulk_modify_tags import TagAction
from src.domain.splits import check_payer_percentage


def _validate_payer_pct(v: int | None) -> int | None:
    if v is not None:
        check_payer_percentage(v)
    return v


def _validate_non_empty[T](v: list[T], label: str) -> list[T]:
    if not v:
        raise ValueError(f"At least one {label} is required")
    return v


class SplitEntryRequest(BaseModel):
    transaction_id: UUID
    payer_percentage: int

    @field_validator("payer_percentage")
    @classmethod
    def validate_range(cls, v: int) -> int:
        check_payer_percentage(v)
        return v


class UpdateSplitsRequest(BaseModel):
    splits: list[SplitEntryRequest]

    @field_validator("splits")
    @classmethod
    def validate_non_empty(cls, v: list[SplitEntryRequest]) -> list[SplitEntryRequest]:
        return _validate_non_empty(v, "split entry")


class UpdateSplitsResponse(BaseModel):
    updated_count: int


class UpdateTransactionRequest(BaseModel):
    date: datetime.date | None = None
    amount: float | None = None
    category: str | None = None
    tags: list[str] | None = None
    payer_percentage: int | None = None
    household: bool | None = None
    is_excluded: bool | None = None
    notes: str | None = None

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
    household: bool | None = None
    is_excluded: bool | None = None
    notes: str | None = None

    @field_validator("transaction_ids")
    @classmethod
    def validate_non_empty(cls, v: list[UUID]) -> list[UUID]:
        return _validate_non_empty(v, "transaction ID")

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
        return _validate_non_empty(v, "transaction ID")

    @field_validator("tags")
    @classmethod
    def validate_tags_non_empty(cls, v: list[str]) -> list[str]:
        return _validate_non_empty(v, "tag")


class BulkModifyTagsResponse(BaseModel):
    updated_count: int
