"""Server-side store for mutation actions awaiting user confirmation.

Two-phase protocol: mutation tools propose an action (stored here),
the frontend renders a confirmation card, and the action executes
only when the user explicitly confirms. Actions expire after 5 minutes.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from attrs import define

from src.domain.exceptions import ActionExpiredError, ForbiddenError

_TTL = timedelta(minutes=5)


@define(frozen=True, slots=True)
class PendingAction:
    action_id: UUID
    person_id: UUID
    tool_name: str
    tool_input: dict[str, object]
    description: str
    details: dict[str, object]
    created_at: datetime


class PendingActionStore:
    """In-memory store for pending mutation confirmations.

    Thread-safe for a single-process async app (no concurrent writers).
    Actions are keyed by UUID and validated against the creating user's
    person_id on claim/cancel.
    """

    def __init__(self) -> None:
        self._actions: dict[UUID, PendingAction] = {}

    def create(
        self,
        person_id: UUID,
        tool_name: str,
        tool_input: dict[str, object],
        description: str,
        details: dict[str, object],
    ) -> PendingAction:
        self._evict_expired()
        action = PendingAction(
            action_id=uuid4(),
            person_id=person_id,
            tool_name=tool_name,
            tool_input=tool_input,
            description=description,
            details=details,
            created_at=datetime.now(UTC),
        )
        self._actions[action.action_id] = action
        return action

    def claim(self, action_id: UUID, person_id: UUID) -> PendingAction:
        """Retrieve and remove a pending action for execution.

        Raises ActionExpiredError if not found (expired or never existed).
        Raises ForbiddenError if the action belongs to a different user.
        """
        self._evict_expired()
        action = self._actions.get(action_id)
        if action is None:
            raise ActionExpiredError("This action has expired. Please try again.")
        if action.person_id != person_id:
            raise ForbiddenError("Cannot confirm another person's action")
        del self._actions[action_id]
        return action

    def cancel(self, action_id: UUID, person_id: UUID) -> None:
        """Remove a pending action without executing it."""
        self._evict_expired()
        action = self._actions.get(action_id)
        if action is None:
            return  # Already expired or cancelled — idempotent
        if action.person_id != person_id:
            raise ForbiddenError("Cannot cancel another person's action")
        del self._actions[action_id]

    def _evict_expired(self) -> None:
        cutoff = datetime.now(UTC) - _TTL
        expired = [aid for aid, a in self._actions.items() if a.created_at < cutoff]
        for aid in expired:
            del self._actions[aid]


pending_action_store = PendingActionStore()
