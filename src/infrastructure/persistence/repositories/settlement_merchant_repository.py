from uuid import UUID

from src.domain.entities.settlement_merchant import SettlementMerchant
from src.infrastructure.persistence.models.settlement_merchant_model import (
    SettlementMerchantModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class SettlementMerchantRepository(
    BaseRepository[SettlementMerchant, SettlementMerchantModel]
):
    _model_class = SettlementMerchantModel

    @staticmethod
    def _to_domain(model: SettlementMerchantModel) -> SettlementMerchant:
        return SettlementMerchant(
            id=UUID(model.id),
            name=model.name,
            merchant_pattern=model.merchant_pattern,
        )

    @staticmethod
    def _to_model(entity: SettlementMerchant) -> SettlementMerchantModel:
        return SettlementMerchantModel(
            id=str(entity.id),
            name=entity.name,
            merchant_pattern=entity.merchant_pattern,
        )
