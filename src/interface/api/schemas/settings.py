from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.entities.settlement_merchant import SettlementMerchant


class CreateSettlementMerchantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    merchant_pattern: str = Field(min_length=2, max_length=100)


class SettlementMerchantResponse(BaseModel):
    id: UUID
    name: str
    merchant_pattern: str

    @classmethod
    def from_domain(cls, entity: SettlementMerchant) -> SettlementMerchantResponse:
        return cls(
            id=entity.id,
            name=entity.name,
            merchant_pattern=entity.merchant_pattern,
        )
