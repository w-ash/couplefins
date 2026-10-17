"""Namespaced tags: labels for consumers.

A namespaced tag has the form `<namespace>:<value>` (for example
`line:mortgage` or `pot:renovation`). It labels a row for a consumer and has
no other effect: it is never a split, reserved, or person-name tag, and an
import never removes one.
"""

from collections.abc import Iterable, Iterator
import re
from typing import Final

_NAMESPACE = r"[a-z][a-z0-9-]*:"
_NAMESPACED_TAG: Final = re.compile(rf"{_NAMESPACE}[a-z0-9][a-z0-9 ._-]*")
_TAG_NAMESPACE: Final = re.compile(_NAMESPACE)


def is_namespaced_tag(tag: str) -> bool:
    """True when the tag is `<namespace>:<value>`."""
    return _NAMESPACED_TAG.fullmatch(tag) is not None


def is_tag_namespace(prefix: str) -> bool:
    """True when the prefix is a namespace with its colon, such as `line:`."""
    return _TAG_NAMESPACE.fullmatch(prefix) is not None


def namespaced_tags(tags: Iterable[str]) -> tuple[str, ...]:
    """The namespaced tags among `tags`, in their order."""
    return tuple(tag for tag in tags if is_namespaced_tag(tag))


def merge_namespaced_tags(
    incoming: Iterable[str], existing: Iterable[str]
) -> tuple[str, ...]:
    """Return `incoming` with the namespaced tags of `existing` that it lacks.

    The incoming tags stay as they are, in their order. The missing
    namespaced tags follow, in their stored order, each once.
    """
    kept = tuple(incoming)
    missing = dict.fromkeys(t for t in namespaced_tags(existing) if t not in kept)
    return (*kept, *missing)


def _values_in(tags: Iterable[str], prefix: str) -> Iterator[str]:
    """The values of the well-formed tags in the `prefix` namespace, in order.

    `prefix` is already validated, so a prefix check is enough; the value's
    first character must still open the grammar (no `pot: bills`).
    """
    return (
        tag.removeprefix(prefix)
        for tag in tags
        if tag.startswith(prefix) and is_namespaced_tag(tag)
    )


def has_tag_prefix(tags: Iterable[str], prefix: str) -> bool:
    """True when a tag in `tags` has a value in the `prefix` namespace.

    `prefix` must be a namespace (`is_tag_namespace`).
    """
    return any(True for _ in _values_in(tags, prefix))


def tag_value(tags: Iterable[str], prefix: str) -> str | None:
    """The value of the first tag in the `prefix` namespace, or None.

    `prefix` must be a namespace (`is_tag_namespace`).
    """
    return next(_values_in(tags, prefix), None)
