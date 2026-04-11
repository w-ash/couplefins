from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

_MAX_CONTENT_PER_MESSAGE = 20_480  # 20 KB
_MAX_TOTAL_CONTENT = 102_400  # 100 KB


class ChatMessageInput(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=_MAX_CONTENT_PER_MESSAGE)


class ConfirmationInput(BaseModel):
    action_id: str
    approved: bool


class ChatRequest(BaseModel):
    messages: list[ChatMessageInput] = Field(..., max_length=50)
    confirmation: ConfirmationInput | None = None

    @model_validator(mode="after")
    def _check_total_content_size(self) -> Self:
        total = sum(len(m.content) for m in self.messages)
        if total > _MAX_TOTAL_CONTENT:
            msg = f"Total message content ({total} bytes) exceeds {_MAX_TOTAL_CONTENT} byte limit"
            raise ValueError(msg)
        return self
