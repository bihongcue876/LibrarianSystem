"""`ReservationRepository` 接口（预约记录）。"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.domain.entities.reservation import Reservation


@runtime_checkable
class ReservationRepository(Protocol):
    """预约持久化接口。"""

    def find_by_id(self, reservation_id: int) -> Reservation | None: ...

    def find_active_by_title(self, title_id: int) -> Sequence[Reservation]:
        """取该题录的**有效**预约队列（`ACTIVE` + `READY`），按 `created_at` 升序（BR-021）。"""

    def find_active_by_reader(self, reader_id: int) -> Sequence[Reservation]:
        """取该读者的全部有效预约——额度占用计算用（BR-007）。"""

    def find_by_reader(self, reader_id: int) -> Sequence[Reservation]:
        """取该读者全部预约记录（含历史）。"""

    def add(self, reservation: Reservation) -> Reservation: ...

    def update(self, reservation: Reservation) -> None: ...
