import re
from typing import Final


class CoupleDefaults:
    EXPECTED_PERSON_COUNT: Final = 2


class SplitDefaults:
    DEFAULT_PAYER_PERCENTAGE: Final = 50
    MAX_PAYER_PERCENTAGE: Final = 100


class SharedTags:
    TAGS: Final = frozenset({"shared", "split"})
    SPLIT_TAG_PATTERN: Final = re.compile(r"^s(\d{1,3})$")


class HouseholdTags:
    TAGS: Final = frozenset({"household"})


class SettlementTags:
    TAGS: Final = frozenset({"settlement"})


# Tags that are never treated as person names during spotted detection.
RESERVED_TAGS: Final = SharedTags.TAGS | HouseholdTags.TAGS | SettlementTags.TAGS
