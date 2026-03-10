import re
from typing import Final


class SplitDefaults:
    DEFAULT_PAYER_PERCENTAGE: Final = 50
    MAX_PAYER_PERCENTAGE: Final = 100


class SharedTags:
    TAGS: Final = frozenset({"shared", "split"})
    SPLIT_TAG_PATTERN: Final = re.compile(r"^s(\d{1,3})$")
