from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from src.domain.entities.account import ACCOUNT_KINDS, Account
from src.domain.literals import parse_literal
from src.infrastructure.persistence.models.account_model import AccountModel
from src.infrastructure.persistence.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account, AccountModel]):
    _model_class = AccountModel

    @staticmethod
    def _to_domain(model: AccountModel) -> Account:
        return Account(
            id=UUID(model.id),
            name=model.name,
            kind=parse_literal(model.kind, ACCOUNT_KINDS, "account kind"),
            owner_person_id=(
                UUID(model.owner_person_id) if model.owner_person_id else None
            ),
        )

    @staticmethod
    def _to_model(entity: Account) -> AccountModel:
        return AccountModel(**AccountRepository._to_column_values(entity))

    @staticmethod
    def _to_column_values(entity: Account) -> dict[str, object]:
        return {
            "id": str(entity.id),
            "name": entity.name,
            "kind": entity.kind,
            "owner_person_id": (
                str(entity.owner_person_id) if entity.owner_person_id else None
            ),
        }

    async def add_missing(self, entities: list[Account]) -> None:
        """Insert the accounts that do not exist yet; leave the others unchanged.

        One statement, and safe when a concurrent import adds the same account.
        """
        if not entities:
            return
        stmt = (
            insert(AccountModel)
            .values([self._to_column_values(e) for e in entities])
            .on_conflict_do_nothing()
        )
        await self._execute_rowcount(stmt)
