from uuid import UUID

from attrs import define

_MIN_PATTERN_LENGTH = 2


@define(frozen=True, slots=True)
class SettlementMerchant:
    id: UUID
    name: str
    merchant_pattern: str

    def __attrs_post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if len(self.merchant_pattern) < _MIN_PATTERN_LENGTH:
            raise ValueError(
                f"merchant_pattern must be at least {_MIN_PATTERN_LENGTH} characters"
            )
