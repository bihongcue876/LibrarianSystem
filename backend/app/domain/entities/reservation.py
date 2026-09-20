"""Reservation 实体（`05-domain-model.md` §6.1、`06-domain-class-diagram.md` 图 5）。

**聚合根**，指向 `BookTitle`（不是副本）。

有效期 7 天（BR-025）：`ACTIVE` 自 `created_at` 起算，`READY` 自 `ready_at` 起算——
**两种状态两个起算点**，这是容易实现错的地方。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from app.domain.enums import ReservationStatus
from app.domain.exceptions import ValidationError

DEFAULT_VALIDITY_DAYS = 7


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Reservation:
    """预约记录。"""

    def __init__(
        self,
        reservation_id: int | None = None,
        reader_id: int | None = None,
        title_id: int | None = None,
        created_at: datetime | None = None,
        status: ReservationStatus | str = ReservationStatus.ACTIVE,
        ready_at: datetime | None = None,
        expired_at: datetime | None = None,
    ) -> None:
        self.reservation_id = reservation_id
        self.reader_id = reader_id
        self.title_id = title_id
        self.created_at = created_at or utc_now()
        self._status = ReservationStatus(status)
        self.ready_at = ready_at
        self.expired_at = expired_at

    @property
    def status(self) -> ReservationStatus:
        return self._status

    # ---- 构造 ------------------------------------------------------------

    @classmethod
    def create(cls, reader, title, now: datetime | None = None) -> "Reservation":
        """创建预约，状态 `ACTIVE`。`created_at` 决定排队顺序（BR-021）。"""
        return cls(
            reader_id=getattr(reader, "reader_id", None),
            title_id=getattr(title, "title_id", None),
            created_at=now or utc_now(),
            status=ReservationStatus.ACTIVE,
        )

    @classmethod
    def rehydrate(cls, **kwargs) -> "Reservation":
        """**仅供 Mapper 从持久化状态重建**。"""
        return cls(**kwargs)

    # ---- 状态流转 --------------------------------------------------------

    def mark_ready(self, now: datetime | None = None) -> None:
        """到书可借：`ACTIVE` → `READY`，写入 `ready_at`（BR-024a）。"""
        if self._status is not ReservationStatus.ACTIVE:
            raise ValidationError(
                f"仅 `ACTIVE` 可标记到书，当前为 {self._status.value}",
                code="RESERVATION_NOT_ACTIVE",
            )
        self._status = ReservationStatus.READY
        self.ready_at = now or utc_now()

    def cancel(self) -> None:
        """取消预约。**`ACTIVE` 与 `READY` 均可取消**（BR-025a）。"""
        if not self._status.is_cancellable:
            raise ValidationError(
                f"当前状态 {self._status.value} 不可取消", code="RESERVATION_NOT_CANCELLABLE"
            )
        self._status = ReservationStatus.CANCELLED

    def expire(self, now: datetime | None = None) -> None:
        """置为失效（BR-025）。"""
        if self._status in (ReservationStatus.EXPIRED, ReservationStatus.CANCELLED):
            raise ValidationError(
                f"当前状态 {self._status.value} 不可失效", code="RESERVATION_NOT_EXPIRABLE"
            )
        self._status = ReservationStatus.EXPIRED
        self.expired_at = now or utc_now()

    # ---- 判定 ------------------------------------------------------------

    def is_active(self) -> bool:
        """是否为有效预约（`ACTIVE`/`READY`）——占用 1 个借阅额度（BR-026）。"""
        return self._status.is_effective

    def validity_start(self) -> datetime:
        """有效期起算点：`READY` 自 `ready_at` 起算，其余自 `created_at` 起算（BR-025）。"""
        if self._status is ReservationStatus.READY and self.ready_at is not None:
            return self.ready_at
        return self.created_at

    def expires_at(self, validity_days: int = DEFAULT_VALIDITY_DAYS) -> datetime:
        return self.validity_start() + timedelta(days=validity_days)

    def is_expired(self, now: datetime | None = None, validity_days: int = DEFAULT_VALIDITY_DAYS) -> bool:
        """是否已过有效期（**惰性判定**，不依赖定时任务，BR-025 / Q-01）。"""
        if not self.is_active():
            return False
        return (now or utc_now()) >= self.expires_at(validity_days)

    def queue_position(self, reservations: Sequence["Reservation"]) -> int:
        """在队列中的位置（从 1 开始）。非有效预约或不在队列中返回 0。

        排序**按 `created_at` 升序**，不依赖自增主键（BR-021）。
        """
        if not self.is_active():
            return 0
        ordered = sorted(
            (res for res in reservations if res.is_active()),
            key=lambda res: (res.created_at, res.reservation_id or 0),
        )
        for index, res in enumerate(ordered, start=1):
            if res.reservation_id is not None and res.reservation_id == self.reservation_id:
                return index
            if res is self:
                return index
        return 0

    def __str__(self) -> str:  # pragma: no cover
        return f"Reservation(id={self.reservation_id}, {self._status.value})"

    def __repr__(self) -> str:  # pragma: no cover
        return self.__str__()
