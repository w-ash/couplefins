import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.application.use_cases.bulk_modify_tags import TagAction
from src.domain.split_rules import check_owner_shares, check_payer_percentage
from src.interface.api.schemas.types import MoneyField


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


class TransactionChangesRequest(BaseModel):
    """The fields both transaction PATCH routes change. Omitted (or null)
    leaves a field as it is, except where noted."""

    category: str | None = None
    payer_percentage: int | None = None
    household: bool | None = None
    is_excluded: bool | None = None
    notes: str | None = None
    # Joint rows only. Omitted leaves the value; null clears it.
    depositor_person_id: UUID | None = None
    owner_shares: dict[UUID, int] | None = None

    @field_validator("payer_percentage")
    @classmethod
    def validate_payer_percentage(cls, v: int | None) -> int | None:
        if v is not None:
            check_payer_percentage(v)
        return v

    @field_validator("owner_shares")
    @classmethod
    def validate_owner_shares(cls, v: dict[UUID, int] | None) -> dict[UUID, int] | None:
        if v is not None:
            check_owner_shares(v)
        return v


class UpdateTransactionRequest(TransactionChangesRequest):
    date: datetime.date | None = None
    amount: MoneyField | None = None
    tags: list[str] | None = None


class TransactionEditResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    transaction_id: UUID
    field_name: str
    old_value: str
    new_value: str
    edited_at: datetime.datetime
    edited_by_person_id: UUID | None


class ImportEventResponse(BaseModel):
    model_config = {"from_attributes": True}

    person_id: UUID
    imported_at: datetime.datetime


class TransactionEditHistoryResponse(BaseModel):
    import_event: ImportEventResponse | None
    edits: list[TransactionEditResponse]


class UpdateTransactionResponse(BaseModel):
    id: UUID
    edits: list[TransactionEditResponse]


class BulkUpdateRequest(TransactionChangesRequest):
    transaction_ids: list[UUID]

    @field_validator("transaction_ids")
    @classmethod
    def validate_non_empty(cls, v: list[UUID]) -> list[UUID]:
        return _validate_non_empty(v, "transaction ID")


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
