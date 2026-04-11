from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageInput(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConfirmationInput(BaseModel):
    action_id: str
    approved: bool


class ChatRequest(BaseModel):
    messages: list[ChatMessageInput] = Field(..., max_length=50)
    confirmation: ConfirmationInput | None = None
