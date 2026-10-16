from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.account import Account, AccountKind


class AccountResponse(BaseModel):
    id: UUID
    name: str
    kind: AccountKind
    owner_person_id: UUID | None

    @classmethod
    def from_domain(cls, account: Account) -> AccountResponse:
        return cls(
            id=account.id,
            name=account.name,
            kind=account.kind,
            owner_person_id=account.owner_person_id,
        )


class AccountsResponse(BaseModel):
    accounts: list[AccountResponse]


class MarkAccountJointRequest(BaseModel):
    """A source account label to mark joint, as the import file names it."""

    label: str


class MarkAccountJointResponse(BaseModel):
    """The joint account, the rows moved into it, and the twin rows dropped
    because both partners had imported them."""

    account: AccountResponse
    moved_count: int
    dropped_count: int


class UnmarkAccountJointResponse(BaseModel):
    """How many rows returned to the partners who imported them."""

    moved_count: int
