"""`FineRepository` 的 SQLAlchemy 实现。

金额列由 `MoneyType` 以 TEXT 存储；求和**在应用层用 `Decimal` 完成**，
因为数据库层对 TEXT 无法做数值聚合（`13` §4.11 已披露该代价）。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.fine_record import FineRecord
from app.domain.enums import FineStatus
from app.domain.value_objects.money import Money
from app.infrastructure.mappers import FineMapper
from app.infrastructure.models import FineRecordModel

UNPAID = FineStatus.UNPAID.value


class SqlAlchemyFineRepository:
    """实现 `application.ports.FineRepository`。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, fine_id: int) -> FineRecord | None:
        model = self._session.get(FineRecordModel, fine_id)
        return FineMapper.to_domain(model) if model else None

    def find_unpaid_by_reader(self, reader_id: int) -> Sequence[FineRecord]:
        models = self._session.scalars(
            select(FineRecordModel).where(
                FineRecordModel.reader_id == reader_id,
                FineRecordModel.status == UNPAID,
            )
        ).all()
        return [FineMapper.to_domain(model) for model in models]

    def find_by_reader(self, reader_id: int) -> Sequence[FineRecord]:
        models = self._session.scalars(
            select(FineRecordModel)
            .where(FineRecordModel.reader_id == reader_id)
            .order_by(FineRecordModel.created_at.desc(), FineRecordModel.fine_id.desc())
        ).all()
        return [FineMapper.to_domain(model) for model in models]

    def sum_unpaid_by_reader(self, reader_id: int) -> str:
        models = self._session.scalars(
            select(FineRecordModel).where(
                FineRecordModel.reader_id == reader_id,
                FineRecordModel.status == UNPAID,
            )
        ).all()
        total = Decimal("0.00")
        for model in models:
            total += (model.amount if isinstance(model.amount, Money) else Money.parse(model.amount)).amount
        return str(total.quantize(Decimal("0.01")))

    def add(self, record: FineRecord) -> FineRecord:
        model = FineMapper.to_model(record)
        self._session.add(model)
        self._session.flush()
        record.fine_id = model.fine_id
        return record

    def update(self, record: FineRecord) -> None:
        if record.fine_id is None:
            return
        model = self._session.get(FineRecordModel, record.fine_id)
        if model is None:
            return
        FineMapper.to_model(record, model)
