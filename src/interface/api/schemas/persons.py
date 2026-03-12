from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.application.use_cases.export_adjustments import PreviewAdjustmentsResult
from src.domain.entities.person import Person

_NAME_MAX = 50


class SetupCoupleRequest(BaseModel):
    name1: str = Field(max_length=_NAME_MAX)
    name2: str = Field(max_length=_NAME_MAX)

    @field_validator("name1", "name2")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name must not be blank")
        return v


class UpdatePersonRequest(BaseModel):
    adjustment_account: str

    @field_validator("adjustment_account")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Adjustment account must not be blank")
        return v


class PersonResponse(BaseModel):
    id: UUID
    name: str
    adjustment_account: str

    @classmethod
    def from_domain(cls, person: Person) -> PersonResponse:
        return cls(
            id=person.id,
            name=person.name,
            adjustment_account=person.adjustment_account,
        )


class AdjustmentResponse(BaseModel):
    dedup_id: str
    date: str
    merchant: str
    category: str
    amount: float


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
                    amount=float(a.amount),
                )
                for a in result.adjustments
            ],
            person_name=result.person_name,
            adjustment_count=result.adjustment_count,
        )
