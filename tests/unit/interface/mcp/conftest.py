"""Shared fixtures for the MCP interface tests.

The pending-action store lives as a module global in BOTH
``src.interface.mcp.confirmation`` (the claim/commit binding) and
``src.application.chat.tool_executor`` (the propose path). A test store
must be patched at both import sites together — a partial patch silently
tests the wrong store — so the swap is defined once, here.
"""

import pytest

from src.application.chat import tool_executor
from src.application.chat.pending_actions import PendingAction, PendingActionStore
from src.interface.mcp import confirmation


def settle_args(amount: float = 50.0) -> dict[str, object]:
    """The canonical record_settlement payload for MCP tests."""
    return {"from_person": "Alice", "to_person": "Bob", "amount": amount}


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> PendingActionStore:
    """A fresh store patched at both consumer import sites."""
    fresh = PendingActionStore()
    monkeypatch.setattr(confirmation, "pending_action_store", fresh)
    monkeypatch.setattr(tool_executor, "pending_action_store", fresh)
    return fresh


@pytest.fixture
def committed(monkeypatch: pytest.MonkeyPatch) -> list[PendingAction]:
    """Stub the DB-backed commit; record the claimed action it received."""
    seen: list[PendingAction] = []

    async def _fake_commit(
        action: PendingAction, current_user: object
    ) -> tuple[dict[str, object], str | None]:
        seen.append(action)
        return {"status": "confirmed", "description": "done"}, "settlements"

    monkeypatch.setattr(confirmation, "execute_confirmed_action", _fake_commit)
    return seen
