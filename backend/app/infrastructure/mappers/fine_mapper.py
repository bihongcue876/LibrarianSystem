"""`FineRecord` ↔ `fine_records` 表。金额经 `MoneyType` 走 TEXT 列。"""

from __future__ import annotations

from app.domain.entities.fine_record import FineRecord
from app.domain.enums import FineStatus
from app.domain.value_objects.money import Money
from app.infrastructure.mappers._time import to_db, to_domain
from app.infrastructure.models import FineRecordModel


class FineMapper:
    """罚款记录双向转换。"""

    @staticmethod
    def to_domain(model: FineRecordModel) -> FineRecord:
        return FineRecord.rehydrate(
            fine_id=model.fine_id,
            loan_id=model.loan_id,
            reader_id=model.reader_id,
            amount=model.amount if isinstance(model.amount, Money) else Money.parse(model.amount),
            overdue_days=model.overdue_days,
            billed_days=model.billed_days,
            unit_price=(
                model.unit_price
                if isinstance(model.unit_price, Money)
                else Money.parse(model.unit_price)
            ),
            status=FineStatus(model.status),
            created_at=to_domain(model.created_at),
            paid_at=to_domain(model.paid_at),
            operator_id=model.operator_id,
            operator_role=model.operator_role,
        )

    @staticmethod
    def to_model(record: FineRecord, model: FineRecordModel | None = None) -> FineRecordModel:
        target = model or FineRecordModel()
        target.fine_id = record.fine_id
        target.loan_id = record.loan_id
        target.reader_id = record.reader_id
        target.amount = record.amount
        target.overdue_days = record.overdue_days
        target.billed_days = record.billed_days
        target.unit_price = record.unit_price
        target.status = record.status.value
        target.created_at = to_db(record.created_at)
        target.paid_at = to_db(record.paid_at)
        target.operator_id = record.operator_id
        target.operator_role = record.operator_role
        return target
