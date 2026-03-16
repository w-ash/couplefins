from datetime import UTC, datetime
from decimal import Decimal
import uuid

import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_decimal,
    positive_int,
)
from src.application.use_cases._shared.settlement_records import (
    validate_settlement_persons,
)
from src.domain.entities.settlement import Settlement, SettlementMethod
from src.domain.entities.settlement_transaction_link import SettlementTransactionLink
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class RecordSettlementCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)
    amount: Decimal = field(validator=positive_decimal)
    from_person_id: uuid.UUID
    to_person_id: uuid.UUID
    method: SettlementMethod
    notes: str = ""
    settled_at: datetime | None = None
    linked_transaction_ids: list[uuid.UUID] = field(factory=list)


@define(frozen=True, slots=True)
class RecordSettlementResult:
    settlement: Settlement


@define(slots=True)
class RecordSettlementUseCase:
    async def execute(
        self, command: RecordSettlementCommand, uow: UnitOfWorkProtocol
    ) -> RecordSettlementResult:
        async with uow:
            await validate_settlement_persons(
                command.from_person_id, command.to_person_id, uow
            )

            linked_txs: list[Transaction] = []
            if command.linked_transaction_ids:
                linked_txs = await uow.transactions.get_by_ids(
                    command.linked_transaction_ids
                )
                found_ids = {tx.id for tx in linked_txs}
                missing = set(command.linked_transaction_ids) - found_ids
                if missing:
                    raise NotFoundError(f"Transactions not found: {missing}")

            now = datetime.now(UTC)
            settlement = Settlement(
                id=uuid.uuid4(),
                year=command.year,
                month=command.month,
                amount=command.amount,
                from_person_id=command.from_person_id,
                to_person_id=command.to_person_id,
                method=command.method,
                is_waived=False,
                notes=command.notes,
                settled_at=command.settled_at or now,
                created_at=now,
            )
            saved = await uow.settlements.save(settlement)

            if linked_txs:
                links = [
                    SettlementTransactionLink(
                        id=uuid.uuid4(),
                        settlement_id=saved.id,
                        transaction_id=tx_id,
                    )
                    for tx_id in command.linked_transaction_ids
                ]
                await uow.settlement_transaction_links.save_batch(links)

                for tx in linked_txs:
                    if not tx.is_settlement:
                        updated = attrs.evolve(tx, is_settlement=True)
                        await uow.transactions.update_mutable_fields(updated)

            await uow.commit()
            return RecordSettlementResult(settlement=saved)
