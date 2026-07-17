"""Two-phase confirmation wrapper for MCP write tools.

Drives ``handle_write_call`` through the real ``record_settlement`` propose
path (DB-free when no transactions are linked) and a real
``PendingActionStore``, monkeypatching only the final commit
(``execute_confirmed_action`` — the DB-backed step, already covered by the
chat suite). Locks the guarantees: preview never mutates, confirm commits
once, expired/malformed token re-previews, args drift is rejected.
"""

from uuid import UUID, uuid4

import pytest

from src.application.chat.pending_actions import PendingAction, PendingActionStore
from src.application.chat.registry import _SPECS_BY_NAME
from src.domain.exceptions import ToolExecutionError
from src.interface.mcp import confirmation
from tests.fixtures.factories import ALICE, BOB
from tests.fixtures.fake_llm_client import make_tool_context
from tests.unit.interface.mcp.conftest import settle_args as _settle_args

_CTX = make_tool_context(ALICE, [ALICE, BOB])
_SPEC = _SPECS_BY_NAME["record_settlement"]


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

    async def test_explicit_null_confirm_previews(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        """Schema-driven clients serialize every declared optional as an
        explicit JSON null — null means omitted, i.e. preview."""
        result = await confirmation.handle_write_call(
            _SPEC,
            {**_settle_args(), "confirm": None, "confirm_token": None},
            _CTX,
        )
        assert result["status"] == "needs_confirmation"
        assert committed == []

    async def test_non_boolean_confirm_is_rejected(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        """bool("false") is True — a truthy string from a nonconforming
        client must never route to the commit path (the low-level MCP
        server does not validate arguments against the schema)."""
        preview = await confirmation.handle_write_call(_SPEC, _settle_args(), _CTX)
        with pytest.raises(ToolExecutionError, match="JSON boolean"):
            await confirmation.handle_write_call(
                _SPEC,
                {
                    **_settle_args(),
                    "confirm": "false",
                    "confirm_token": preview["confirm_token"],
                },
                _CTX,
            )
        assert committed == []


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

    async def test_token_from_another_tool_is_rejected(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        """The store keys actions by id alone — a token minted by tool A's
        preview must never commit through a call naming tool B, even when
        the argument dicts happen to match. The rejection must not consume
        the token: A's preview stays pending and confirmable."""
        preview = await confirmation.handle_write_call(_SPEC, _settle_args(), _CTX)
        token = preview["confirm_token"]

        other_spec = _SPECS_BY_NAME["waive_settlement"]
        with pytest.raises(ToolExecutionError, match="belongs to record_settlement"):
            await confirmation.handle_write_call(
                other_spec,
                {**_settle_args(), "confirm": True, "confirm_token": token},
                _CTX,
            )
        assert committed == []

        # The original preview survived the mistaken cross-tool call.
        result = await confirmation.handle_write_call(
            _SPEC,
            {**_settle_args(), "confirm": True, "confirm_token": token},
            _CTX,
        )
        assert result["status"] == "confirmed"
        assert len(committed) == 1

    async def test_null_valued_optionals_are_not_drift(
        self, store: PendingActionStore, committed: list[PendingAction]
    ) -> None:
        """Explicit JSON nulls for optionals omitted at preview are the same
        request — the commit runs the stored propose-time input either way,
        so rejecting them would only burn the token for nothing."""
        preview = await confirmation.handle_write_call(_SPEC, _settle_args(), _CTX)

        result = await confirmation.handle_write_call(
            _SPEC,
            {
                **_settle_args(),
                "year": None,
                "month": None,
                "notes": None,
                "confirm": True,
                "confirm_token": preview["confirm_token"],
            },
            _CTX,
        )
        assert result["status"] == "confirmed"
        assert len(committed) == 1

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
