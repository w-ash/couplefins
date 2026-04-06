from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.application.use_cases.export_adjustments import PreviewAdjustmentsResult
from src.domain.entities.person import Person
from src.interface.api.schemas.types import MoneyField

_NAME_MAX = 50


class SetupCoupleRequest(BaseModel):
    name1: str = Field(max_length=_NAME_MAX)
    name2: str = Field(max_length=_NAME_MAX)
    password1: str
    password2: str

    @field_validator("name1", "name2")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name must not be blank")
        return v


class UpdatePersonRequest(BaseModel):
    adjustment_account: str | None = None
    theme_preference: str | None = None

    @field_validator("adjustment_account")
    @classmethod
    def must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Adjustment account must not be blank")
        return v

    @field_validator("theme_preference")
    @classmethod
    def valid_theme(cls, v: str | None) -> str | None:
        if v is not None and v not in {"system", "light", "dark"}:
            raise ValueError("theme_preference must be system, light, or dark")
        return v


class PersonResponse(BaseModel):
    id: UUID
    name: str
    adjustment_account: str
    theme_preference: str

    @classmethod
    def from_domain(cls, person: Person) -> PersonResponse:
        return cls(
            id=person.id,
            name=person.name,
            adjustment_account=person.adjustment_account,
            theme_preference=person.theme_preference,
        )


class AdjustmentResponse(BaseModel):
    dedup_id: str
    date: str
    merchant: str
    category: str
    amount: MoneyField


class AdjustmentPreviewResponse(BaseModel):
    adjustments: list[AdjustmentResponse]
    person_name: str
    adjustment_count: int

    @classmethod
    def from_result(cls, result: PreviewAdjustmentsResult) -> AdjustmentPreviewResponse:
        return cls(
            adjustments=[
                AdjustmentResponse(
                    dedup_id=a.dedup_id,
                    date=a.date.isoformat(),
                    merchant=a.merchant,
                    category=a.category,
                    amount=a.amount,
                )
                for a in result.adjustments
            ],
            person_name=result.person_name,
            adjustment_count=result.adjustment_count,
        )
