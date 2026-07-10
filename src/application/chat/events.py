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


@dataclass(frozen=True, slots=True)
class ServerToolStartEvent:
    """Emitted when the API starts a server-side tool (code execution)."""

    name: str
    tool_use_id: str
    input: dict[str, object]


@dataclass(frozen=True, slots=True)
class ServerToolResultEvent:
    """Emitted when a server-side code execution finishes."""

    tool_use_id: str
    stdout: str
    stderr: str
    return_code: int
