from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.transaction import Transaction
from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from tests.fixtures.factories import make_account


async def save_transactions(
    session: AsyncSession, transactions: list[Transaction]
) -> list[Transaction]:
    """Save transactions and the personal account each one names."""
    accounts = {
        tx.account_id: make_account(
            id=tx.account_id, name=tx.account, owner_person_id=tx.payer_person_id
        )
        for tx in transactions
    }
    await AccountRepository(session).save_batch(list(accounts.values()))
    return await TransactionRepository(session).save_batch(transactions)
