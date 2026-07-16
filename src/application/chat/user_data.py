"""User-data marking — the chat prompt-injection defense convention.

Free-text values that originate from the couple (merchant names,
categories, tags, notes, filenames, settlement-merchant names/patterns)
must reach the model labeled as data, never as instructions. The
convention has one marker and three boundaries:

- **Marker**: handlers mark user-originated strings with :class:`UserData`,
  a ``str`` subclass carrying the RAW value. Nothing is wrapped at
  construction time — the same summary dict can safely feed every consumer.
- **Model boundary (wrap)**: serializing a tool result into model context
  (the tool-result loop in ``use_case.py``, the confirm-context injection in
  ``routes/chat.py``) runs :func:`wrap_for_model`, which encloses UserData
  values in ``<user_data>`` tags.
- **Frontend boundary (strip)**: ToolResultEvent summaries pass through
  :func:`strip_user_data` before they reach the SSE stream, so the frontend
  renders raw values and needs no strip sites of its own.
- **Input boundary (sanitize)**: ``registry.execute_tool`` applies
  :func:`strip_user_data` to every incoming tool_input, so wrapped values
  the model echoes back can never break lookups or persist.

The tag literals live ONLY in this module (plus the prompt text that
teaches the model the convention).

Accepted residuals: sandbox stdout and the assistant's own prose re-enter
model context unmarked by construction — the prompts instruct the model to
keep treating wrapped values as data there and to strip tags when quoting.
(Subagent summaries stopped being a residual in v1.9.1: run_subagent marks
its whole summary as UserData, so it re-enters the write-capable main
model wrapped.)
"""

import re
from typing import cast

_TAG_RE = re.compile(r"</?user_data>")


class UserData(str):
    """Marks a string as user-originated untrusted data (raw value)."""

    __slots__ = ()


def wrap(value: str) -> str:
    """Enclose a value in ``<user_data>`` tags for model-facing text.

    Any tag literals embedded in the value are removed first, so a value
    like ``X</user_data>IGNORE...`` cannot break out of its wrapper.
    """
    return f"<user_data>{_TAG_RE.sub('', value)}</user_data>"


def wrap_for_model(obj: object) -> object:
    """Recursively wrap :class:`UserData` values for model serialization.

    Non-mutating: containers are rebuilt, never modified in place — the
    pending-confirmation ``details`` dict is the same object stored in the
    PendingActionStore and must keep its raw values.
    """
    if isinstance(obj, UserData):
        return wrap(obj)
    if isinstance(obj, dict):
        items = cast(dict[object, object], obj)
        return {wrap_for_model(k): wrap_for_model(v) for k, v in items.items()}
    if isinstance(obj, list):
        return [wrap_for_model(v) for v in cast(list[object], obj)]
    if isinstance(obj, tuple):
        return tuple(wrap_for_model(v) for v in cast(tuple[object, ...], obj))
    return obj


def strip_user_data(obj: object) -> object:
    """Recursively remove all ``<user_data>`` tag literals from strings.

    Applied to outgoing event summaries (frontend boundary) and incoming
    tool inputs (input sanitizer). Rebuilds containers, including dict keys.
    """
    if isinstance(obj, str):
        return _TAG_RE.sub("", obj)
    if isinstance(obj, dict):
        items = cast(dict[object, object], obj)
        return {strip_user_data(k): strip_user_data(v) for k, v in items.items()}
    if isinstance(obj, list):
        return [strip_user_data(v) for v in cast(list[object], obj)]
    if isinstance(obj, tuple):
        return tuple(strip_user_data(v) for v in cast(tuple[object, ...], obj))
    return obj
