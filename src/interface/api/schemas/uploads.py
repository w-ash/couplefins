from datetime import date
from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases.preview_csv import PreviewCsvResult, PreviewTransaction
from src.application.use_cases.upload_csv import UploadCsvResult


class PreviewTransactionResponse(BaseModel):
    date: date
    merchant: str
    category: str
    amount: float
    is_shared: bool
    payer_percentage: int | None


class FieldDiffResponse(BaseModel):
    field_name: str
    old_value: str
    new_value: str


class ChangedTransactionResponse(BaseModel):
    existing_id: UUID
    incoming: PreviewTransactionResponse
    existing: PreviewTransactionResponse
    diffs: list[FieldDiffResponse]


class PreviewUploadResponse(BaseModel):
    new_transactions: list[PreviewTransactionResponse]
    unchanged_count: int
    changed_transactions: list[ChangedTransactionResponse]
    unmapped_categories: list[str]

    @classmethod
    def from_result(cls, result: PreviewCsvResult) -> PreviewUploadResponse:
        def _tx_response(tx: PreviewTransaction) -> PreviewTransactionResponse:
            return PreviewTransactionResponse(
                date=tx.date,
                merchant=tx.merchant,
                category=tx.category,
                amount=float(tx.amount),
                is_shared=tx.is_shared,
                payer_percentage=tx.payer_percentage,
            )

        return cls(
            new_transactions=[_tx_response(tx) for tx in result.new_transactions],
            unchanged_count=result.unchanged_count,
            changed_transactions=[
                ChangedTransactionResponse(
                    existing_id=ct.existing_id,
                    incoming=_tx_response(ct.incoming),
                    existing=_tx_response(ct.existing),
                    diffs=[
                        FieldDiffResponse(
                            field_name=d.field_name,
                            old_value=d.old_value,
                            new_value=d.new_value,
                        )
                        for d in ct.diffs
                    ],
                )
                for ct in result.changed_transactions
            ],
            unmapped_categories=result.unmapped_categories,
        )


class UploadSummaryResponse(BaseModel):
    upload_id: UUID
    filename: str
    new_count: int
    updated_count: int
    skipped_count: int
    unmapped_categories: list[str]

    @classmethod
    def from_result(cls, result: UploadCsvResult) -> UploadSummaryResponse:
        return cls(
            upload_id=result.upload_id,
            filename=result.filename,
            new_count=result.new_count,
            updated_count=result.updated_count,
            skipped_count=result.skipped_count,
            unmapped_categories=result.unmapped_categories,
        )
