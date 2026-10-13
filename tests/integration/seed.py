from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.transaction import Transaction
from src.domain.parsing.importer import accounts_named_by
from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)


async def save_transactions(
    session: AsyncSession, transactions: list[Transaction]
) -> list[Transaction]:
    """Save transactions and the personal account each one names."""
    await AccountRepository(session).add_missing(accounts_named_by(transactions))
    return await TransactionRepository(session).save_batch(transactions)
