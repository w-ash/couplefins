from uuid import UUID

from sqlalchemy import select

from src.domain.entities.account import Account, parse_account_kind
from src.infrastructure.persistence.models.account_model import AccountModel
from src.infrastructure.persistence.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account, AccountModel]):
    _model_class = AccountModel

    @staticmethod
    def _to_domain(model: AccountModel) -> Account:
        return Account(
            id=UUID(model.id),
            name=model.name,
            kind=parse_account_kind(model.kind),
            owner_person_id=(
                UUID(model.owner_person_id) if model.owner_person_id else None
            ),
        )

    @staticmethod
    def _to_model(entity: Account) -> AccountModel:
        return AccountModel(
            id=str(entity.id),
            name=entity.name,
            kind=entity.kind,
            owner_person_id=(
                str(entity.owner_person_id) if entity.owner_person_id else None
            ),
        )

    async def get_by_owner(self, owner_person_id: UUID) -> list[Account]:
        stmt = select(AccountModel).where(
            AccountModel.owner_person_id == str(owner_person_id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]
