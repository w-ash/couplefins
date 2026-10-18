import datetime
from uuid import UUID

import attrs
from pydantic import BaseModel, ConfigDict, computed_field

from src.application.use_cases._shared.command_validators import (
    as_validation_error,
    build_validated,
)
from src.application.use_cases._shared.house_records import (
    LoanTerms,
    ObligationTerms,
)
from src.application.use_cases.add_loan_payment_obligations import (
    AddLoanPaymentObligationsCommand,
)
from src.application.use_cases.close_loan import CloseLoanCommand
from src.application.use_cases.create_loan import CreateLoanCommand
from src.application.use_cases.create_obligation import CreateObligationCommand
from src.application.use_cases.get_house import GetHouseResult
from src.application.use_cases.mark_obligation_paid import MarkObligationPaidCommand
from src.application.use_cases.record_manual_transaction import (
    RecordManualTransactionCommand,
)
from src.application.use_cases.replace_loan import ReplaceLoanCommand
from src.application.use_cases.save_co_owned_asset import SaveCoOwnedAssetCommand
from src.application.use_cases.update_loan_statement import (
    UpdateLoanStatementCommand,
)
from src.application.use_cases.update_obligation import UpdateObligationCommand
from src.domain.capital import share_kind
from src.domain.constants import DEFAULT_MANUAL_ACCOUNT, LOAN_TAG_PREFIX
from src.domain.entities.co_owned_asset import (
    ContributionKind,
    CoOwnedAsset,
    ordered_kinds,
)
from src.domain.entities.loan import LoanKind
from src.domain.entities.obligation import ObligationKind, ObligationStatus
from src.domain.entities.transaction import Transaction
from src.domain.house import ActivityKind
from src.domain.obligations import PaymentCandidate
from src.interface.api.schemas.dashboard import DashboardPersonResponse
from src.interface.api.schemas.types import MoneyField, PercentField


class _HouseModel(BaseModel):
    """Validates straight from frozen attrs records: the ``src.domain.house``
    figures, the loan and obligation entities, and use case results."""

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


class _LoanFiguresResponse(_HouseModel):
    """What an open and a past loan both show."""

    id: UUID
    name: str
    lender: str
    kind: LoanKind
    principal: MoneyField
    balance: MoneyField  # statement_balance less the principal paid since
    rate_percent: PercentField
    payment: MoneyField
    statement_balance: MoneyField
    statement_balance_as_of: datetime.date


class LoanResponse(_LoanFiguresResponse):
    """An open loan."""

    next_due: datetime.date | None  # None once the term has run out, all paid
    owner_parts: list[OwnerAmountResponse]  # sum to payment


class PastLoanResponse(_LoanFiguresResponse):
    """A closed or replaced loan, kept with its history."""

    closed_on: datetime.date
    replaced_by_loan_id: UUID | None  # None when closed without a refinance


class ObligationResponse(_HouseModel):
    id: UUID
    name: str
    kind: ObligationKind
    status: ObligationStatus  # on the as-of date
    amount: MoneyField
    is_estimate: bool
    due: datetime.date
    late_after: datetime.date | None
    pays_from: str | None
    loan_id: UUID | None
    paid_by_transaction_id: UUID | None
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
    loans: list[LoanResponse]  # the open loans
    past_loans: list[PastLoanResponse]
    upcoming: list[ObligationResponse]  # unpaid, ascending by due
    recent_paid: list[ObligationResponse]  # paid, newest due first
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


class LoanRecordResponse(_HouseModel):
    """A loan as entered. ``tag`` (`loan:<slug>`) links its payment rows;
    ``annual_rate`` is a percent."""

    id: UUID
    name: str
    slug: str
    lender: str
    kind: LoanKind
    principal: MoneyField
    annual_rate: PercentField
    payment: MoneyField
    term_months: int | None
    first_due_on: datetime.date
    statement_balance: MoneyField
    statement_balance_as_of: datetime.date
    replaced_by_loan_id: UUID | None
    closed_on: datetime.date | None
    notes: str
    created_at: datetime.datetime

    @computed_field
    @property
    def tag(self) -> str:
        return f"{LOAN_TAG_PREFIX}{self.slug}"


class ReplaceLoanResponse(_HouseModel):
    replaced: LoanRecordResponse  # closed, naming its replacement
    replacement: LoanRecordResponse


class LoanTermsRequest(BaseModel):
    """A new loan's terms. The command and the loan check the values (a 422
    when they fail)."""

    name: str
    lender: str
    kind: LoanKind
    principal: MoneyField
    annual_rate: PercentField  # a percent: 6.5 for 6.5%
    payment: MoneyField  # the scheduled monthly payment
    term_months: int | None = None
    first_due_on: datetime.date
    statement_balance: MoneyField
    statement_balance_as_of: datetime.date
    notes: str = ""

    def to_terms(self) -> LoanTerms:
        return build_validated(
            LoanTerms, self.model_dump(include=set(LoanTermsRequest.model_fields))
        )


class CreateLoanRequest(LoanTermsRequest):
    def to_command(self) -> CreateLoanCommand:
        return CreateLoanCommand(terms=self.to_terms())


class ReplaceLoanRequest(LoanTermsRequest):
    """The replacing loan's terms, and the day the old loan closes."""

    closed_on: datetime.date

    def to_command(self, loan_id: UUID) -> ReplaceLoanCommand:
        return ReplaceLoanCommand(
            loan_id=loan_id, closed_on=self.closed_on, replacement=self.to_terms()
        )


class CloseLoanRequest(BaseModel):
    closed_on: datetime.date

    def to_command(self, loan_id: UUID) -> CloseLoanCommand:
        return CloseLoanCommand(loan_id=loan_id, closed_on=self.closed_on)


class LoanStatementRequest(BaseModel):
    """The balance on the servicer's statement of ``as_of``."""

    balance: MoneyField
    as_of: datetime.date

    def to_command(self, loan_id: UUID) -> UpdateLoanStatementCommand:
        return UpdateLoanStatementCommand(
            loan_id=loan_id, balance=self.balance, as_of=self.as_of
        )


class LoanPaymentObligationsRequest(BaseModel):
    months: int  # how many monthly payments to add, 1-24

    def to_command(self, loan_id: UUID) -> AddLoanPaymentObligationsCommand:
        return as_validation_error(
            AddLoanPaymentObligationsCommand, loan_id=loan_id, months=self.months
        )


class ObligationRecordResponse(_HouseModel):
    """An obligation as entered; ``paid_by_transaction_id`` is the row that
    paid it, None while unpaid."""

    id: UUID
    kind: ObligationKind
    description: str
    amount: MoneyField
    is_estimate: bool
    due_on: datetime.date
    late_after: datetime.date | None
    pays_from: str | None
    loan_id: UUID | None
    paid_by_transaction_id: UUID | None
    notes: str


class ObligationTermsRequest(BaseModel):
    """An obligation's values, all but the row that paid it. The command
    and the obligation check them (a 422 when they fail)."""

    kind: ObligationKind
    description: str
    amount: MoneyField  # what is due, > 0
    is_estimate: bool = False  # not yet billed
    due_on: datetime.date
    late_after: datetime.date | None = None  # the delinquency date
    pays_from: str | None = None  # a pot's or an account's name
    loan_id: UUID | None = None  # required for, and only for, a loan_payment
    notes: str = ""

    def to_terms(self) -> ObligationTerms:
        return build_validated(ObligationTerms, self.model_dump())


class CreateObligationRequest(ObligationTermsRequest):
    def to_command(self) -> CreateObligationCommand:
        return CreateObligationCommand(terms=self.to_terms())


class UpdateObligationRequest(ObligationTermsRequest):
    def to_command(self, obligation_id: UUID) -> UpdateObligationCommand:
        return UpdateObligationCommand(
            obligation_id=obligation_id, terms=self.to_terms()
        )


class ObligationPaymentRequest(BaseModel):
    transaction_id: UUID | None  # the row that paid it; None marks it unpaid

    def to_command(self, obligation_id: UUID) -> MarkObligationPaidCommand:
        return MarkObligationPaidCommand(
            obligation_id=obligation_id, transaction_id=self.transaction_id
        )


class ObligationCandidateResponse(BaseModel):
    """A row that may pay an obligation. ``score`` adds 3 for an amount
    within $1 or 2%, 2 for a date within a week of the due date (1 within
    30 days), and 2 for the obligation's loan tag."""

    id: UUID
    date: datetime.date
    merchant: str
    account_name: str
    category: str
    amount: MoneyField  # signed: negative = money out
    payer_person_id: UUID | None  # None for a joint row
    score: int

    @classmethod
    def from_domain(cls, candidate: PaymentCandidate) -> ObligationCandidateResponse:
        tx = candidate.transaction
        return cls(
            id=tx.id,
            date=tx.date,
            merchant=tx.merchant,
            account_name=tx.account,
            category=tx.category,
            amount=tx.amount,
            payer_person_id=tx.payer_person_id,
            score=candidate.score,
        )
