from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import exists, select

from src.domain.entities.loan import LOAN_KINDS, Loan
from src.domain.literals import parse_literal
from src.infrastructure.persistence.models.loan_model import LoanModel
from src.infrastructure.persistence.repositories.base import (
    BaseRepository,
    optional_str,
    optional_uuid,
)


class LoanRepository(BaseRepository[Loan, LoanModel]):
    _model_class = LoanModel

    @staticmethod
    def _to_domain(model: LoanModel) -> Loan:
        return Loan(
            id=UUID(model.id),
            asset_id=UUID(model.asset_id),
            name=model.name,
            slug=model.slug,
            lender=model.lender,
            kind=parse_literal(model.kind, LOAN_KINDS, "loan kind"),
            principal=Decimal(model.principal),
            annual_rate=Decimal(model.annual_rate),
            payment=Decimal(model.payment),
            term_months=model.term_months,
            first_due_on=date.fromisoformat(model.first_due_on),
            statement_balance=Decimal(model.statement_balance),
            statement_balance_as_of=date.fromisoformat(model.statement_balance_as_of),
            replaced_by_loan_id=optional_uuid(model.replaced_by_loan_id),
            closed_on=date.fromisoformat(model.closed_on) if model.closed_on else None,
            notes=model.notes,
            created_at=datetime.fromisoformat(model.created_at),
        )

    @staticmethod
    def _to_model(entity: Loan) -> LoanModel:
        return LoanModel(
            id=str(entity.id),
            asset_id=str(entity.asset_id),
            name=entity.name,
            slug=entity.slug,
            lender=entity.lender,
            kind=entity.kind,
            principal=str(entity.principal),
            annual_rate=str(entity.annual_rate),
            payment=str(entity.payment),
            term_months=entity.term_months,
            first_due_on=entity.first_due_on.isoformat(),
            statement_balance=str(entity.statement_balance),
            statement_balance_as_of=entity.statement_balance_as_of.isoformat(),
            replaced_by_loan_id=optional_str(entity.replaced_by_loan_id),
            closed_on=entity.closed_on.isoformat() if entity.closed_on else None,
            notes=entity.notes,
            created_at=entity.created_at.isoformat(),
        )

    async def get_by_asset_id(self, asset_id: UUID) -> list[Loan]:
        """The asset's loans, open and closed, in the order they were created."""
        stmt = (
            select(LoanModel)
            .where(LoanModel.asset_id == str(asset_id))
            .order_by(LoanModel.created_at, LoanModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_slug(self, slug: str) -> Loan | None:
        stmt = select(LoanModel).where(LoanModel.slug == slug)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def exists_replaced_by(self, loan_id: UUID) -> bool:
        """True when a loan names `loan_id` as the loan that replaced it."""
        stmt = select(exists().where(LoanModel.replaced_by_loan_id == str(loan_id)))
        result = await self._session.execute(stmt)
        return result.scalar_one()
