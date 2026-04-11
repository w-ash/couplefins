from uuid import UUID

from sqlalchemy import func, select

from src.domain.entities.person import Person
from src.infrastructure.persistence.models.person_model import PersonModel
from src.infrastructure.persistence.repositories.base import BaseRepository


class PersonRepository(BaseRepository[Person, PersonModel]):
    _model_class = PersonModel

    @staticmethod
    def _to_domain(model: PersonModel) -> Person:
        return Person(
            id=UUID(model.id),
            name=model.name,
            adjustment_account=model.adjustment_account,
            password_hash=model.password_hash,
            theme_preference=model.theme_preference,
            chat_voice=model.chat_voice,
        )

    @staticmethod
    def _to_model(entity: Person) -> PersonModel:
        return PersonModel(
            id=str(entity.id),
            name=entity.name,
            adjustment_account=entity.adjustment_account,
            password_hash=entity.password_hash,
            theme_preference=entity.theme_preference,
            chat_voice=entity.chat_voice,
        )

    async def get_by_name(self, name: str) -> Person | None:
        stmt = select(PersonModel).where(func.lower(PersonModel.name) == name.lower())
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        return self._to_domain(model) if model else None
