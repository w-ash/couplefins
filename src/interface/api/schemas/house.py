import datetime
from uuid import UUID

import attrs
from pydantic import BaseModel, ConfigDict

from src.application.use_cases._shared.command_validators import (
    as_validation_error,
)
from src.application.use_cases.get_house import GetHouseResult
from src.application.use_cases.record_manual_transaction import (
    RecordManualTransactionCommand,
)
from src.application.use_cases.save_co_owned_asset import SaveCoOwnedAssetCommand
from src.domain.capital import share_kind
from src.domain.constants import DEFAULT_MANUAL_ACCOUNT
from src.domain.entities.co_owned_asset import (
    ContributionKind,
    CoOwnedAsset,
    ordered_kinds,
)
from src.domain.entities.transaction import Transaction
from src.domain.house import (
    ActivityKind,
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
    is_unassigned: bool  # the money that no pot names


class OwnerDepositsResponse(_HouseModel):
    person_id: UUID
    own_deposits: MoneyField
    gift_deposits: MoneyField
    share_of_payments: MoneyField
    unspent: MoneyField  # own + gift - share of payments


class SetAsideSectionResponse(_HouseModel):
    buckets: list[BucketResponse]
    total: MoneyField
    bank_balance: MoneyField | None  # the joint accounts', last read from the bank
    bank_balance_as_of: datetime.date | None
    difference: MoneyField | None  # bank_balance - total
    owners: list[OwnerDepositsResponse]  # one per owner, in persons order


class ActivityRowResponse(_HouseModel):
    id: UUID
    date: datetime.date
    account_name: str
    person_id: UUID | None  # the depositor of a deposit
    kind: ActivityKind
    budget_line: str | None
    amount: MoneyField  # signed: negative = money out
    shares: list[OwnerAmountResponse]  # sum to |amount|


class CoOwnedAssetResponse(BaseModel):
    """The couple's home and the settings of their shares in it."""

    id: UUID
    name: str
    repair_threshold: MoneyField  # a repair counts from this amount up
    qualifying_kinds: list[ContributionKind]  # in ContributionKind order
    bank_balance: MoneyField | None  # last read from the bank
    bank_balance_as_of: datetime.date | None
    created_at: datetime.datetime

    @classmethod
    def from_domain(cls, asset: CoOwnedAsset) -> CoOwnedAssetResponse:
        return cls(
            id=asset.id,
            name=asset.name,
            repair_threshold=asset.repair_threshold,
            qualifying_kinds=ordered_kinds(asset.qualifying_kinds),
            bank_balance=asset.bank_balance,
            bank_balance_as_of=asset.bank_balance_as_of,
            created_at=asset.created_at,
        )


class SaveCoOwnedAssetRequest(BaseModel):
    """The whole asset: a save replaces every setting. The command checks
    the values (a 422 when they fail)."""

    name: str
    repair_threshold: MoneyField
    qualifying_kinds: list[ContributionKind]
    bank_balance: MoneyField | None = None
    bank_balance_as_of: datetime.date | None = None

    def to_command(self) -> SaveCoOwnedAssetCommand:
        return as_validation_error(
            SaveCoOwnedAssetCommand,
            name=self.name,
            repair_threshold=self.repair_threshold,
            qualifying_kinds=frozenset(self.qualifying_kinds),
            bank_balance=self.bank_balance,
            bank_balance_as_of=self.bank_balance_as_of,
        )


class RecordManualTransactionRequest(BaseModel):
    """A contribution that passed through no imported account. The command
    and the use case check the values (a 422 when they fail)."""

    account_name: str = DEFAULT_MANUAL_ACCOUNT
    date: datetime.date
    amount: MoneyField  # what was paid, > 0
    description: str
    document_ref: str = ""
    share_kind: ContributionKind
    owner_shares: dict[UUID, int]  # each owner's percentage; sum to 100

    def to_command(self, entered_by: UUID) -> RecordManualTransactionCommand:
        return as_validation_error(
            RecordManualTransactionCommand,
            account_name=self.account_name,
            date=self.date,
            amount=self.amount,
            description=self.description,
            document_ref=self.document_ref,
            share_kind=self.share_kind,
            owner_shares=self.owner_shares,
            entered_by_person_id=entered_by,
        )


class ManualEntryResponse(BaseModel):
    """A hand-entered row. ``share_kind`` is None when its `share:` tag was
    edited away or names no kind; ``owner_shares`` is None when cleared
    (then 50/50)."""

    id: UUID
    account_name: str
    date: datetime.date
    amount: MoneyField  # what was paid: the row's amount, as money out
    description: str
    document_ref: str
    share_kind: ContributionKind | None
    owner_shares: dict[UUID, int] | None

    @classmethod
    def from_domain(cls, tx: Transaction) -> ManualEntryResponse:
        return cls(
            id=tx.id,
            account_name=tx.account,
            date=tx.date,
            amount=-tx.amount,
            description=tx.merchant,
            document_ref=tx.notes,
            share_kind=share_kind(tx),
            owner_shares=dict(tx.owner_shares) if tx.owner_shares else None,
        )


class HouseResponse(_HouseModel):
    """Every House figure, precomputed — the client renders, never derives.

    ``example_sections`` names the sections still on the fixed example
    payload, by their field names here; empty once every figure is real.
    ``asset`` is None until the home is set up.
    """

    example_sections: list[str]
    asset: CoOwnedAssetResponse | None
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
            "example_sections": sorted(result.example_sections),
            "asset": (
                CoOwnedAssetResponse.from_domain(result.asset) if result.asset else None
            ),
            **attrs.asdict(result.figures, recurse=False),
        })
