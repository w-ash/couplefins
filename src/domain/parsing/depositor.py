"""Find whose deposit a joint account's incoming row is, from its text."""

from collections.abc import Iterable, Sequence
import re
from uuid import UUID

from src.domain.entities.person import Person


def match_depositor(texts: Iterable[str], persons: Sequence[Person]) -> UUID | None:
    """Return the one person whose name appears in the texts, else None.

    A name matches as a whole word, ignoring case, so a short name does not
    match inside a longer word. No match, or both names, gives None.
    """
    joined = "\n".join(texts)
    matched = [
        p.id
        for p in persons
        if p.name.strip()
        and re.search(rf"\b{re.escape(p.name.strip())}\b", joined, re.IGNORECASE)
    ]
    return matched[0] if len(matched) == 1 else None
