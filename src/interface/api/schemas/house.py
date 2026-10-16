import datetime
from uuid import UUID

import attrs
from pydantic import BaseModel, ConfigDict

from src.application.use_cases.get_house import GetHouseResult
from src.domain.house import (
    ActivityKind,
    ContributionKind,
    LoanKind,
    ObligationKind,
)
from src.interface.api.schemas.dashboard import DashboardPersonResponse
from src.interface.api.schemas.types import MoneyField, PercentField


class _HouseModel(BaseModel):
    """Validates straight from the frozen ``src.domain.house`` records."""

    model_config = ConfigDict(from_attributes=True)


class OwnerAmountResponse(_HouseModel):
    person_id: UUID
    amount: MoneyField


class OwnerShareResponse(_HouseModel):
    person_id: UUID
    capital: MoneyField
    percent: PercentField


class PutInKindResponse(_HouseModel):
    kind: ContributionKind
    amounts: list[OwnerAmountResponse]
    total: MoneyField


class PutInSectionResponse(_HouseModel):
    kinds: list[PutInKindResponse]
    totals: list[OwnerAmountResponse]
    total: MoneyField
    unspent_deposits: list[OwnerAmountResponse]


class ShareHistoryPointResponse(_HouseModel):
    year: int
    month: int
    owners: list[OwnerShareResponse]


class SharesSectionResponse(_HouseModel):
    now: list[OwnerShareResponse]
    total_capital: MoneyField
    history: list[ShareHistoryPointResponse]  # ascending; the last point equals now


class LoanResponse(_HouseModel):
    id: UUID
    name: str
    kind: LoanKind
    balance: MoneyField
    rate_percent: PercentField
    payment: MoneyField
    next_due: datetime.date
    owner_parts: list[OwnerAmountResponse]


class ObligationResponse(_HouseModel):
    id: UUID
    name: str
    kind: ObligationKind
    amount: MoneyField
    is_estimate: bool
    due: datetime.date
    late_after: datetime.date | None
    pays_from: str | None
    shortfall: MoneyField | None  # set when the paying bucket falls short


class BucketResponse(_HouseModel):
    name: str
    balance: MoneyField
    bank_balance: MoneyField | None
    bank_balance_as_of: datetime.date | None
    difference: MoneyField | None  # bank_balance - balance


class SetAsideSectionResponse(_HouseModel):
    buckets: list[BucketResponse]
    total: MoneyField


class ActivityRowResponse(_HouseModel):
    id: UUID
    date: datetime.date
    account_name: str
    person_id: UUID | None  # the depositor of a deposit
    kind: ActivityKind
    budget_line: str | None
    amount: MoneyField  # signed: negative = money out
    shares: list[OwnerAmountResponse]  # sum to |amount|


class HouseResponse(_HouseModel):
    """Every House figure, precomputed — the client renders, never derives.

    ``is_example`` is true while the figures are the fixed example payload.
    """

    is_example: bool
    as_of: datetime.date
    persons: list[DashboardPersonResponse]
    put_in: PutInSectionResponse
    shares: SharesSectionResponse
    loans: list[LoanResponse]
    upcoming: list[ObligationResponse]  # ascending by due
    set_aside: SetAsideSectionResponse
    recent_activity: list[ActivityRowResponse]  # newest first

    @classmethod
    def from_result(cls, result: GetHouseResult) -> HouseResponse:
        return cls.model_validate({
            "is_example": result.is_example,
            **attrs.asdict(result.figures, recurse=False),
        })
