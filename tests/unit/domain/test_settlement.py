from decimal import Decimal
import uuid

import pytest

from tests.fixtures.factories import make_settlement, make_settlement_portion


class TestSettlementEntity:
    def test_valid_settlement(self) -> None:
        s = make_settlement()
        assert s.amount == Decimal("50.00")
        assert s.is_waived is False

    def test_negative_amount_raises(self) -> None:
        with pytest.raises(ValueError, match="amount must be >= 0"):
            make_settlement(amount=Decimal("-10.00"))

    def test_zero_amount_valid(self) -> None:
        s = make_settlement(amount=Decimal(0), is_waived=True, method=None)
        assert s.amount == Decimal(0)

    def test_same_person_raises(self) -> None:
        person_id = uuid.uuid4()
        with pytest.raises(ValueError, match="must differ"):
            make_settlement(from_person_id=person_id, to_person_id=person_id)

    def test_waived_settlement(self) -> None:
        s = make_settlement(amount=Decimal(0), is_waived=True, method=None)
        assert s.is_waived is True
        assert s.method is None
        assert s.amount == Decimal(0)


class TestSettlementPortionEntity:
    def test_valid_portion(self) -> None:
        p = make_settlement_portion()
        assert p.year == 2026
        assert p.month == 1
        assert p.amount == Decimal("50.00")

    def test_invalid_month_raises(self) -> None:
        with pytest.raises(ValueError, match="month must be 1-12"):
            make_settlement_portion(month=0)
        with pytest.raises(ValueError, match="month must be 1-12"):
            make_settlement_portion(month=13)

    def test_invalid_year_raises(self) -> None:
        with pytest.raises(ValueError, match="year must be >= 1"):
            make_settlement_portion(year=0)

    def test_non_positive_amount_raises(self) -> None:
        with pytest.raises(ValueError, match="amount must be positive"):
            make_settlement_portion(amount=Decimal(0))
