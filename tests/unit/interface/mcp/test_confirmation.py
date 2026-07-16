"""Two-phase confirmation wrapper for MCP write tools.

Drives ``handle_write_call`` through the real ``record_settlement`` propose
path (DB-free when no transactions are linked) and a real
``PendingActionStore``, monkeypatching only the final commit
(``execute_confirmed_action`` — the DB-backed step, already covered by the
chat suite). Locks the guarantees: preview never mutates, confirm commits
once, expired/malformed token re-previews, args drift is rejected.
"""

import uuid
from uuid import UUID, uuid4

import pytest

from src.application.chat import tool_executor
from src.application.chat.pending_actions import PendingAction, PendingActionStore
from src.application.chat.registry import _SPECS_BY_NAME
from src.domain.exceptions import ToolExecutionError
from src.interface.mcp import confirmation
from tests.fixtures.factories import make_person
from tests.fixtures.fake_llm_client import make_tool_context

ALICE = make_person(name="Alice", id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
BOB = make_person(name="Bob", id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
_CTX = make_tool_context(ALICE, [ALICE, BOB])
_SPEC = _SPECS_BY_NAME["record_settlement"]


def _settle_args(amount: float = 50.0) -> dict[str, object]:
    return {"from_person": "Alice", "to_person": "Bob", "amount": amount}


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> PendingActionStore:
    """A fresh store shared by the propose path and the claim binding."""
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


class TestPreview:
    async def test_first_call_previews_and_stores_without_committing(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        result = await confirmation.handle_write_call(_SPEC, _settle_args(), _CTX)

        assert result["status"] == "needs_confirmation"
        assert result["confirm_token"]
        assert "preview" in result
        # Stored for confirmation, and nothing committed.
        assert store.claim(UUID(str(result["confirm_token"])), ALICE.id)
        assert committed == []


class TestCommit:
    async def test_confirm_with_valid_token_commits_once(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        args = _settle_args()
        preview = await confirmation.handle_write_call(_SPEC, dict(args), _CTX)
        token = preview["confirm_token"]

        result = await confirmation.handle_write_call(
            _SPEC, {**args, "confirm": True, "confirm_token": token}, _CTX
        )
        assert result["status"] == "confirmed"
        assert len(committed) == 1

    async def test_confirm_true_without_token_errors(
        self, store: PendingActionStore
    ) -> None:
        with pytest.raises(ToolExecutionError, match="confirm_token"):
            await confirmation.handle_write_call(
                _SPEC, {**_settle_args(), "confirm": True}, _CTX
            )


class TestExpiredAndDrift:
    async def test_expired_or_unknown_token_re_previews(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        # A well-formed but unknown token → fresh preview, never a stale commit.
        result = await confirmation.handle_write_call(
            _SPEC,
            {**_settle_args(), "confirm": True, "confirm_token": str(uuid4())},
            _CTX,
        )
        assert result["status"] == "needs_confirmation"
        assert committed == []

    async def test_malformed_token_re_previews(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        result = await confirmation.handle_write_call(
            _SPEC,
            {**_settle_args(), "confirm": True, "confirm_token": "not-a-uuid"},
            _CTX,
        )
        assert result["status"] == "needs_confirmation"
        assert committed == []

    async def test_args_drift_is_rejected(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        preview = await confirmation.handle_write_call(
            _SPEC, _settle_args(amount=50.0), _CTX
        )
        token = preview["confirm_token"]

        with pytest.raises(ToolExecutionError, match="Arguments changed"):
            await confirmation.handle_write_call(
                _SPEC,
                {
                    **_settle_args(amount=500.0),  # drifted between calls
                    "confirm": True,
                    "confirm_token": token,
                },
                _CTX,
            )
        assert committed == []

    async def test_other_persons_action_is_forbidden(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        preview = await confirmation.handle_write_call(_SPEC, _settle_args(), _CTX)
        token = preview["confirm_token"]

        bob_ctx = make_tool_context(BOB, [ALICE, BOB])
        with pytest.raises(ToolExecutionError, match="another person"):
            await confirmation.handle_write_call(
                _SPEC,
                {**_settle_args(), "confirm": True, "confirm_token": token},
                bob_ctx,
            )
        assert committed == []
