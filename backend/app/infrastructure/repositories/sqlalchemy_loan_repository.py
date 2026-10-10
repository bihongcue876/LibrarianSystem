"""`LoanRepository` 的 SQLAlchemy 实现。

注意：`OVERDUE` 为派生状态，查询超期时写 `status = 'BORROWED' AND due_at < now`，
**不可**写 `status = 'OVERDUE'`（库里没有这个值）。
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities.loan import Loan
from app.domain.enums import LoanStatus
from app.infrastructure.mappers import LoanMapper
from app.infrastructure.models import LoanModel

PERSISTED_BORROWED = LoanStatus.BORROWED.value


class SqlAlchemyLoanRepository:
    """实现 `application.ports.LoanRepository`。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, loan_id: int) -> Loan | None:
        model = self._session.get(LoanModel, loan_id)
        return LoanMapper.to_domain(model) if model else None

    def find_active_by_item(self, item_id: int) -> Loan | None:
        model = self._session.scalar(
            select(LoanModel).where(
                LoanModel.item_id == item_id,
                LoanModel.status == PERSISTED_BORROWED,
            )
        )
        return LoanMapper.to_domain(model) if model else None

    def find_active_by_reader(self, reader_id: int) -> Sequence[Loan]:
        models = self._session.scalars(
            select(LoanModel).where(
                LoanModel.reader_id == reader_id,
                LoanModel.status == PERSISTED_BORROWED,
            )
        ).all()
        return [LoanMapper.to_domain(model) for model in models]

    def find_by_reader(self, reader_id: int) -> Sequence[Loan]:
        models = self._session.scalars(
            select(LoanModel)
            .where(LoanModel.reader_id == reader_id)
            .order_by(LoanModel.borrowed_at.desc(), LoanModel.loan_id.desc())
        ).all()
        return [LoanMapper.to_domain(model) for model in models]

    def count_active_by_reader(self, reader_id: int) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(LoanModel)
                .where(
                    LoanModel.reader_id == reader_id,
                    LoanModel.status == PERSISTED_BORROWED,
                )
            )
            or 0
        )

    def add(self, loan: Loan) -> Loan:
        model = LoanMapper.to_model(loan)
        self._session.add(model)
        self._session.flush()
        loan.loan_id = model.loan_id
        return loan

    def update(self, loan: Loan) -> None:
        if loan.loan_id is None:
            return
        model = self._session.get(LoanModel, loan.loan_id)
        if model is None:
            return
        LoanMapper.to_model(loan, model)
