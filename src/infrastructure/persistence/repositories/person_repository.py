from uuid import UUID

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
        )

    @staticmethod
    def _to_model(entity: Person) -> PersonModel:
        return PersonModel(
            id=str(entity.id),
            name=entity.name,
            adjustment_account=entity.adjustment_account,
        )
