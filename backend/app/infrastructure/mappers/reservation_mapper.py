"""`Reservation` ↔ `reservations` 表。"""

from __future__ import annotations

from app.domain.entities.reservation import Reservation
from app.domain.enums import ReservationStatus
from app.infrastructure.mappers._time import to_db, to_domain
from app.infrastructure.models import ReservationModel


class ReservationMapper:
    """预约记录双向转换。"""

    @staticmethod
    def to_domain(model: ReservationModel) -> Reservation:
        return Reservation.rehydrate(
            reservation_id=model.reservation_id,
            reader_id=model.reader_id,
            title_id=model.title_id,
            created_at=to_domain(model.created_at),
            status=ReservationStatus(model.status),
            ready_at=to_domain(model.ready_at),
            expired_at=to_domain(model.expired_at),
        )

    @staticmethod
    def to_model(
        reservation: Reservation, model: ReservationModel | None = None
    ) -> ReservationModel:
        target = model or ReservationModel()
        target.reservation_id = reservation.reservation_id
        target.reader_id = reservation.reader_id
        target.title_id = reservation.title_id
        target.created_at = to_db(reservation.created_at)
        target.status = reservation.status.value
        target.ready_at = to_db(reservation.ready_at)
        target.expired_at = to_db(reservation.expired_at)
        return target
