from datetime import date
from decimal import Decimal

import attrs
import pytest

from src.application.use_cases.save_co_owned_asset import (
    SaveCoOwnedAssetCommand,
    SaveCoOwnedAssetUseCase,
)
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import make_co_owned_asset
from tests.fixtures.mocks import make_mock_uow

BASE = SaveCoOwnedAssetCommand(
    name="Home",
    repair_threshold=Decimal(750),
    qualifying_kinds=frozenset({"closing", "repair"}),
    bank_balance=Decimal("1234.567"),
    bank_balance_as_of=date(2026, 10, 1),
)


def _command(**overrides: object) -> SaveCoOwnedAssetCommand:
    """The base command with `overrides`; converters and validators run."""
    return attrs.evolve(BASE, **overrides)


async def _save(command: SaveCoOwnedAssetCommand, current=None):
    uow = make_mock_uow()
    uow.co_owned_assets.get_current.return_value = current
    uow.co_owned_assets.save.side_effect = lambda asset: asset
    result = await SaveCoOwnedAssetUseCase().execute(command, uow)
    return uow, result.asset


class TestSaveCoOwnedAsset:
    """US-HOUSE-9: one asset per couple; saving again updates it."""

    async def test_creates_the_asset_when_none_exists(self) -> None:
        uow, asset = await _save(_command())

        assert (asset.name, asset.repair_threshold) == ("Home", Decimal("750.00"))
        assert asset.qualifying_kinds == {"closing", "repair"}
        assert asset.bank_balance == Decimal("1234.57")
        assert asset.bank_balance_as_of == date(2026, 10, 1)
        uow.co_owned_assets.save.assert_awaited_once_with(asset)
        uow.commit.assert_awaited_once()

    async def test_updates_the_existing_asset_keeping_its_id_and_creation(
        self,
    ) -> None:
        current = make_co_owned_asset(name="Old name")

        _, asset = await _save(
            _command(name="New name", qualifying_kinds=frozenset({"insurance"})),
            current,
        )

        assert (asset.id, asset.created_at) == (current.id, current.created_at)
        assert asset.name == "New name"
        assert asset.qualifying_kinds == {"insurance"}

    async def test_clears_the_bank_balance(self) -> None:
        current = make_co_owned_asset(
            bank_balance=Decimal(10), bank_balance_as_of=date(2026, 9, 1)
        )

        _, asset = await _save(
            _command(bank_balance=None, bank_balance_as_of=None), current
        )

        assert (asset.bank_balance, asset.bank_balance_as_of) == (None, None)

    async def test_no_qualifying_kind_saves(self) -> None:
        """An asset may count nothing yet; every credit is then zero."""
        _, asset = await _save(_command(qualifying_kinds=frozenset()))

        assert asset.qualifying_kinds == frozenset()

    async def test_the_assets_invariant_is_a_validation_error(self) -> None:
        """The entity owns the threshold rule; the use case makes it a 422."""
        uow = make_mock_uow()

        with pytest.raises(ValidationError, match="repair_threshold"):
            await SaveCoOwnedAssetUseCase().execute(
                _command(repair_threshold=Decimal(-1)), uow
            )
        uow.co_owned_assets.save.assert_not_called()


class TestSaveCoOwnedAssetCommand:
    def test_the_name_must_not_be_blank(self) -> None:
        with pytest.raises(ValueError, match="name"):
            _command(name="  ")

    @pytest.mark.parametrize(
        "change",
        [{"bank_balance": None}, {"bank_balance_as_of": None}],
        ids=["no balance", "no date"],
    )
    def test_the_bank_balance_and_its_date_come_together(
        self, change: dict[str, object]
    ) -> None:
        with pytest.raises(ValueError, match="together"):
            _command(**change)
