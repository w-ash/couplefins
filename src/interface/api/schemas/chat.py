from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageInput(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessageInput] = Field(..., max_length=50)
