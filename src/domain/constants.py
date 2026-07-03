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


# Group label for transactions whose category is unmapped (group_id is None).
UNCATEGORIZED_GROUP_NAME: Final = "Uncategorized"


# Tag stamped on exported adjustment rows (see src/domain/export/csv_renderer.py).
# Adjustments are imported into Monarch and come back in the next export —
# the parser skips rows carrying this tag so derived data never re-ingests.
ADJUSTMENT_TAG: Final = "couplefins-adjustment"
