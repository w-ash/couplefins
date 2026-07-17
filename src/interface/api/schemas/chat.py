from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from src.config.settings import EffortLevel

_MAX_CONTENT_PER_MESSAGE = 20_480  # 20 KB
_MAX_TOTAL_CONTENT = 102_400  # 100 KB
_MAX_PAGE_HINT_LENGTH = 64


class ChatMessageInput(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=_MAX_CONTENT_PER_MESSAGE)


class ConfirmationInput(BaseModel):
    action_id: str
    approved: bool


class ChatRequest(BaseModel):
    messages: list[ChatMessageInput] = Field(..., max_length=50)
    confirmation: ConfirmationInput | None = None
    # The browser's local calendar date, so "today"/"this month" resolve to
    # what the user actually sees on their clock — not UTC, which is
    # tomorrow (or next month) for the entire US evening. Falls back to
    # server UTC when absent (headless callers, tests).
    client_date: date | None = None
    # Per-request effort override — the user picks per task in the chat UI
    # (quick lookup vs. deep analysis). Falls back to ChatConfig.effort.
    effort: EffortLevel | None = None
    # The coarse UI section the user is on (e.g. "budget"), so the server
    # can promote that page's tools into the loaded set (registry
    # _PAGE_TOOL_HINTS). Unknown/absent pages promote nothing — the value
    # is a routing hint, never reflected into the prompt verbatim.
    page: str | None = None

    @field_validator("page")
    @classmethod
    def _page_is_a_hint(cls, v: str | None) -> str | None:
        """Degrade, never reject: an overlong value is just another unknown
        page and must become None — a 422 here would fail the whole chat
        message over a field that is advisory by design."""
        return v if v is not None and len(v) <= _MAX_PAGE_HINT_LENGTH else None

    @model_validator(mode="after")
    def _check_total_content_size(self) -> Self:
        total = sum(len(m.content) for m in self.messages)
        if total > _MAX_TOTAL_CONTENT:
            msg = f"Total message content ({total} bytes) exceeds {_MAX_TOTAL_CONTENT} byte limit"
            raise ValueError(msg)
        return self
