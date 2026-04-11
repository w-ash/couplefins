"""Chat stream event types — yielded by the chat use case."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TextDelta:
    """Incremental text from the LLM."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolStartEvent:
    """Emitted when the model invokes a tool."""

    name: str
    tool_use_id: str


@dataclass(frozen=True, slots=True)
class ToolResultEvent:
    """Emitted after a tool executes."""

    name: str
    tool_use_id: str
    summary: dict[str, object]
    is_error: bool = field(default=False)
