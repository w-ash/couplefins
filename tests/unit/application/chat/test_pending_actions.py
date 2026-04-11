"""Tests for the PendingActionStore."""

from datetime import UTC, datetime, timedelta
import uuid

import pytest

from src.application.chat.pending_actions import PendingAction, PendingActionStore
from src.domain.exceptions import ActionExpiredError, ForbiddenError

ALICE_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _make_store() -> PendingActionStore:
    return PendingActionStore()


def _create_action(
    store: PendingActionStore, person_id: uuid.UUID = ALICE_ID
) -> PendingAction:
    return store.create(
        person_id=person_id,
        tool_name="update_budget",
        tool_input={"group_name": "Food & Dining", "amount": 700},
        description="Set Food & Dining to $700.00",
        details={"group_name": "Food & Dining", "amount": 700},
    )


def test_create_and_claim_succeeds() -> None:
    store = _make_store()
    action = _create_action(store)
    claimed = store.claim(action.action_id, ALICE_ID)
    assert claimed.action_id == action.action_id
    assert claimed.tool_name == "update_budget"


def test_claim_removes_action() -> None:
    store = _make_store()
    action = _create_action(store)
    store.claim(action.action_id, ALICE_ID)

    with pytest.raises(ActionExpiredError):
        store.claim(action.action_id, ALICE_ID)


def test_claim_wrong_person_raises_forbidden() -> None:
    store = _make_store()
    action = _create_action(store, person_id=ALICE_ID)

    with pytest.raises(ForbiddenError, match="another person"):
        store.claim(action.action_id, BOB_ID)


def test_claim_expired_raises() -> None:
    store = _make_store()
    action = _create_action(store)

    # Backdate the action to make it expired
    expired_action = PendingAction(
        action_id=action.action_id,
        person_id=action.person_id,
        tool_name=action.tool_name,
        tool_input=action.tool_input,
        description=action.description,
        details=action.details,
        created_at=datetime.now(UTC) - timedelta(minutes=6),
    )
    store._actions[action.action_id] = expired_action

    with pytest.raises(ActionExpiredError, match="expired"):
        store.claim(action.action_id, ALICE_ID)


def test_cancel_removes_action() -> None:
    store = _make_store()
    action = _create_action(store)
    store.cancel(action.action_id, ALICE_ID)

    with pytest.raises(ActionExpiredError):
        store.claim(action.action_id, ALICE_ID)


def test_cancel_idempotent_on_missing() -> None:
    store = _make_store()
    # Cancelling a nonexistent action should not raise
    store.cancel(uuid.uuid4(), ALICE_ID)


def test_cancel_wrong_person_raises_forbidden() -> None:
    store = _make_store()
    action = _create_action(store, person_id=ALICE_ID)

    with pytest.raises(ForbiddenError):
        store.cancel(action.action_id, BOB_ID)


def test_evict_expired_on_create() -> None:
    store = _make_store()

    # Create an old action
    old_action = _create_action(store)
    old = PendingAction(
        action_id=old_action.action_id,
        person_id=old_action.person_id,
        tool_name=old_action.tool_name,
        tool_input=old_action.tool_input,
        description=old_action.description,
        details=old_action.details,
        created_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    store._actions[old_action.action_id] = old

    # Creating a new action should evict the old one
    _create_action(store)
    assert old_action.action_id not in store._actions
