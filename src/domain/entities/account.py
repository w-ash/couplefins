from typing import Final, Literal, get_args
import uuid
from uuid import UUID

from attrs import define

# Who owns the money in an account. A `personal` account has one owner, the
# person whose import it came from. A `joint` account belongs to both owners
# and has no single owner.
AccountKind = Literal["personal", "joint"]
ACCOUNT_KINDS: tuple[AccountKind, ...] = get_args(AccountKind)


def personal_account_id(owner_person_id: UUID, label: str) -> UUID:
    """Return the id of the owner's personal account for a source account label.

    The id derives from the owner and the label, so every import of a label
    names the same account without a lookup.
    """
    return uuid.uuid5(owner_person_id, label)


# Fixed namespace for joint account ids; arbitrary, but must never change.
JOINT_ACCOUNT_NAMESPACE: Final = UUID("4f1c9a52-7e3b-5d08-a6c4-2b9e0d7f8a13")


def joint_account_id(label: str) -> UUID:
    """Return the id of the joint account for a source account label.

    The id derives from the label alone, so both owners' imports of the label
    name the same account.
    """
    return uuid.uuid5(JOINT_ACCOUNT_NAMESPACE, label)


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
