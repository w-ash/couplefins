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


# Namespaces of the labels (namespaced tags, see src/domain/tags.py) that
# couplefins reads.
# A joint row's budget line.
LINE_TAG_PREFIX: Final = "line:"
# The pot of a joint deposit, payment, or pot-to-pot transfer leg.
POT_TAG_PREFIX: Final = "pot:"
# Where a joint deposit's money came from: a gift to the depositor when
# tagged `source:gift`, else the depositor's own money.
SOURCE_TAG_PREFIX: Final = "source:"
SOURCE_GIFT: Final = "gift"
# The pot of a joint row that carries no pot tag. Capitalized, so no `pot:`
# tag (tags are stored lowercased) can name it.
UNASSIGNED_POT: Final = "Unassigned"


# Group label for transactions whose category is unmapped (group_id is None).
UNCATEGORIZED_GROUP_NAME: Final = "Uncategorized"


# Tag stamped on exported adjustment rows (see src/domain/export/csv_renderer.py).
# Adjustments are imported into Monarch and come back in the next export —
# the parser skips rows carrying this tag so derived data never re-ingests.
ADJUSTMENT_TAG: Final = "couplefins-adjustment"
