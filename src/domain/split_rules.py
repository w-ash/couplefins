"""Value rules for a row's split fields.

A leaf module: the Transaction entity checks itself with these, so this
module imports no entity.
"""

from collections.abc import Collection, Mapping
from uuid import UUID

from src.domain.constants import CoupleDefaults, SplitDefaults


def is_joint_payer(payer_person_id: UUID | None) -> bool:
    """True when a row has no payer: a joint account's row.

    Call `filters.is_joint_row` on a transaction. This form is for the
    entity's own checks.
    """
    return payer_person_id is None


def check_payer_percentage(pct: int) -> None:
    """Raise ValueError if payer_percentage is outside 0-MAX_PAYER_PERCENTAGE."""
    if not (0 <= pct <= SplitDefaults.MAX_PAYER_PERCENTAGE):
        raise ValueError(
            f"payer_percentage must be 0-{SplitDefaults.MAX_PAYER_PERCENTAGE}, got {pct}"
        )


def check_owner_shares(
    shares: Mapping[UUID, int], couple: Collection[UUID] | None = None
) -> None:
    """Raise ValueError unless the shares name two owners, each 0-100,
    summing to 100. When `couple` is given, the owners must be its persons.
    """
    if len(shares) != CoupleDefaults.EXPECTED_PERSON_COUNT:
        raise ValueError(
            f"owner_shares must name {CoupleDefaults.EXPECTED_PERSON_COUNT} owners, "
            f"got {len(shares)}"
        )
    if couple is not None and set(shares) != set(couple):
        raise ValueError("owner_shares must name each of the couple")
    for pct in shares.values():
        check_payer_percentage(pct)
    if sum(shares.values()) != SplitDefaults.MAX_PAYER_PERCENTAGE:
        raise ValueError(
            f"owner_shares must sum to {SplitDefaults.MAX_PAYER_PERCENTAGE}, "
            f"got {sum(shares.values())}"
        )
