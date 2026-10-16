from attrs import define

from src.application.use_cases._shared.house_example import EXAMPLE_HOUSE
from src.domain.house import HouseFigures
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetHouseCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class GetHouseResult:
    """Every House figure, precomputed — the UI renders, never derives.

    ``is_example`` is true while ``figures`` is the fixed example payload;
    the page says so until the real figures replace it.
    """

    figures: HouseFigures
    is_example: bool


@define(slots=True)
class GetHouseUseCase:
    async def execute(
        self, _command: GetHouseCommand, _uow: UnitOfWorkProtocol
    ) -> GetHouseResult:
        return GetHouseResult(figures=EXAMPLE_HOUSE, is_example=True)
