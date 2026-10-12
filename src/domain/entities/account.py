from typing import Literal, cast, get_args
from uuid import UUID

from attrs import define

# Who owns the money in an account. A `personal` account has one owner, the
# person whose import it came from. A `joint` account belongs to both owners
# and has no single owner.
AccountKind = Literal["personal", "joint"]


def parse_account_kind(raw: str) -> AccountKind:
    """Narrow a stored string to AccountKind at the persistence boundary."""
    if raw in get_args(AccountKind):
        return cast(AccountKind, raw)
    raise ValueError(f"Unknown account kind: {raw!r}")


@define(frozen=True, slots=True)
class Account:
    id: UUID
    name: str
    kind: AccountKind
    owner_person_id: UUID | None

    def __attrs_post_init__(self) -> None:
        if (self.kind == "personal") != (self.owner_person_id is not None):
            raise ValueError(
                "A personal account must have an owner and a joint account none"
            )
