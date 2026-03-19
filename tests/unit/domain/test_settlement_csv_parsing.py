import uuid

from src.domain.parsing.monarch_csv import parse_monarch_csv

HEADERS = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"


def _csv(tags: str, amount: str = "-50.00") -> str:
    if "," in tags:
        tags = f'"{tags}"'
    return HEADERS + f"2026-01-15,Venmo,Transfer,Chase,VENMO,,{amount},{tags}\n"


class TestSettlementTagParsing:
    def test_settlement_tag_sets_is_settlement(self) -> None:
        txs = parse_monarch_csv(_csv("settlement"), uuid.uuid4(), uuid.uuid4())
        assert len(txs) == 1
        assert txs[0].is_settlement is True
        assert txs[0].payer_percentage == 100
        assert txs[0].household is False

    def test_settlement_tag_case_insensitive(self) -> None:
        txs = parse_monarch_csv(_csv("Settlement"), uuid.uuid4(), uuid.uuid4())
        assert txs[0].is_settlement is True

    def test_settlement_overrides_shared(self) -> None:
        txs = parse_monarch_csv(_csv("shared, settlement"), uuid.uuid4(), uuid.uuid4())
        assert txs[0].is_settlement is True
        assert txs[0].household is False
        assert txs[0].payer_percentage == 100

    def test_no_settlement_tag(self) -> None:
        txs = parse_monarch_csv(_csv("shared"), uuid.uuid4(), uuid.uuid4())
        assert txs[0].is_settlement is False
        assert txs[0].household is True

    def test_empty_tags_not_settlement(self) -> None:
        txs = parse_monarch_csv(_csv(""), uuid.uuid4(), uuid.uuid4())
        assert txs[0].is_settlement is False
