"""`Loan` ↔ `loans` 表。`OVERDUE` 不落库，读回时按两态重建。"""

from __future__ import annotations

from app.domain.entities.loan import Loan
from app.domain.enums import LoanStatus
from app.infrastructure.mappers._time import to_db, to_domain
from app.infrastructure.models import LoanModel


class LoanMapper:
    """借阅记录双向转换。"""

    @staticmethod
    def to_domain(model: LoanModel) -> Loan:
        status = LoanStatus(model.status)
        if status is LoanStatus.OVERDUE:  # 防御：库中不应存在该值
            status = LoanStatus.BORROWED
        return Loan.rehydrate(
            loan_id=model.loan_id,
            reader_id=model.reader_id,
            item_id=model.item_id,
            borrowed_at=to_domain(model.borrowed_at),
            due_at=to_domain(model.due_at),
            returned_at=to_domain(model.returned_at),
            status=status,
            librarian_id=model.librarian_id,
            renew_count=model.renew_count,
        )

    @staticmethod
    def to_model(loan: Loan, model: LoanModel | None = None) -> LoanModel:
        target = model or LoanModel()
        target.loan_id = loan.loan_id
        target.reader_id = loan.reader_id
        target.item_id = loan.item_id
        target.borrowed_at = to_db(loan.borrowed_at)
        target.due_at = to_db(loan.due_at)
        target.returned_at = to_db(loan.returned_at)
        target.status = loan.persisted_status.value  # 只写两态
        target.librarian_id = loan.librarian_id
        target.renew_count = loan.renew_count
        return target
