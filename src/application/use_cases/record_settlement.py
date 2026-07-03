from datetime import datetime
from decimal import Decimal
import uuid

import attrs
from attrs import Factory, define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_decimal,
    positive_int,
    quantize_cents,
)
from src.application.use_cases._shared.finalization import (
    assert_periods_not_finalized,
)
from src.application.use_cases._shared.settlement_records import (
    assert_transactions_not_linked,
    build_settlement,
    validate_settlement_persons,
)
from src.domain.constants import CoupleDefaults
from src.domain.entities.settlement import Settlement
from src.domain.entities.settlement_transaction_link import SettlementTransactionLink
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class RecordSettlementCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)
    amount: Decimal = field(converter=quantize_cents, validator=positive_decimal)
    from_person_id: uuid.UUID
    to_person_id: uuid.UUID
    method: str
    notes: str = ""
    settled_at: datetime | None = None
    linked_transaction_ids: list[uuid.UUID] = field(factory=list)


_AMOUNT_MISMATCH_THRESHOLD = Decimal("0.20")


@define(frozen=True, slots=True)
class RecordSettlementResult:
    settlement: Settlement
    warnings: list[str] = Factory(list[str])


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

                await assert_transactions_not_linked(
                    uow, command.linked_transaction_ids
                )

                payer_ids = {tx.payer_person_id for tx in linked_txs}
                if (
                    len(linked_txs) >= CoupleDefaults.EXPECTED_PERSON_COUNT
                    and len(payer_ids) == 1
                ):
                    raise ValidationError(
                        "All linked transactions are from the same person"
                    )

            # Linked transactions may sit in a different month than the
            # settlement (7-day candidate window crosses month boundaries).
            await assert_periods_not_finalized(
                uow,
                {(command.year, command.month)}
                | {(tx.date.year, tx.date.month) for tx in linked_txs},
            )

            warnings: list[str] = []
            if linked_txs:
                best_match = min(
                    abs(abs(tx.amount) - command.amount) for tx in linked_txs
                )
                if best_match > command.amount * _AMOUNT_MISMATCH_THRESHOLD:
                    warnings.append(
                        f"No linked transaction amount is close to "
                        f"settlement amount ${command.amount}"
                    )

            settlement = build_settlement(
                year=command.year,
                month=command.month,
                from_person_id=command.from_person_id,
                to_person_id=command.to_person_id,
                amount=command.amount,
                method=command.method,
                is_waived=False,
                notes=command.notes,
                settled_at=command.settled_at,
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
            return RecordSettlementResult(settlement=saved, warnings=warnings)
