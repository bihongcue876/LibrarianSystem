"""`ReservationRepository` 的 SQLAlchemy 实现。

队列顺序**按 `created_at` 升序，`reservation_id` 作为稳定的次序打破者**（BR-021）。
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.reservation import Reservation
from app.domain.enums import ReservationStatus
from app.infrastructure.mappers import ReservationMapper
from app.infrastructure.models import ReservationModel

EFFECTIVE_STATUSES = (ReservationStatus.ACTIVE.value, ReservationStatus.READY.value)


class SqlAlchemyReservationRepository:
    """实现 `application.ports.ReservationRepository`。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, reservation_id: int) -> Reservation | None:
        model = self._session.get(ReservationModel, reservation_id)
        return ReservationMapper.to_domain(model) if model else None

    def find_active_by_title(self, title_id: int) -> Sequence[Reservation]:
        models = self._session.scalars(
            select(ReservationModel)
            .where(
                ReservationModel.title_id == title_id,
                ReservationModel.status.in_(EFFECTIVE_STATUSES),
            )
            .order_by(ReservationModel.created_at.asc(), ReservationModel.reservation_id.asc())
        ).all()
        return [ReservationMapper.to_domain(model) for model in models]

    def find_active_by_reader(self, reader_id: int) -> Sequence[Reservation]:
        models = self._session.scalars(
            select(ReservationModel)
            .where(
                ReservationModel.reader_id == reader_id,
                ReservationModel.status.in_(EFFECTIVE_STATUSES),
            )
            .order_by(ReservationModel.created_at.asc(), ReservationModel.reservation_id.asc())
        ).all()
        return [ReservationMapper.to_domain(model) for model in models]

    def find_by_reader(self, reader_id: int) -> Sequence[Reservation]:
        models = self._session.scalars(
            select(ReservationModel)
            .where(ReservationModel.reader_id == reader_id)
            .order_by(ReservationModel.created_at.desc(), ReservationModel.reservation_id.desc())
        ).all()
        return [ReservationMapper.to_domain(model) for model in models]

    def add(self, reservation: Reservation) -> Reservation:
        model = ReservationMapper.to_model(reservation)
        self._session.add(model)
        self._session.flush()
        reservation.reservation_id = model.reservation_id
        return reservation

    def update(self, reservation: Reservation) -> None:
        if reservation.reservation_id is None:
            return
        model = self._session.get(ReservationModel, reservation.reservation_id)
        if model is None:
            return
        ReservationMapper.to_model(reservation, model)
