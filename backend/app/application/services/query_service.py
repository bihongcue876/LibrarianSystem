"""`QueryService`（`09-design-model.md` §5）。

**只读查询，不经领域层**——纯查询没有业务规则需要守卫，强行绕行领域层只会
产生"为了分层而分层"的空转。这条设计选择已在 `08-package-diagram.md` §1 披露，
属**有意为之**。

例外：`Loan.is_overdue()` 这类**派生状态判定**仍由领域方法提供，
因为它表达的是业务语义而非数据搬运。
"""

from __future__ import annotations

from datetime import datetime

from app.application.exceptions import ForbiddenError
from app.application.ports import (
    CatalogRepository,
    FineRepository,
    LoanRepository,
    ReaderRepository,
    ReservationRepository,
)
from app.domain.clock import utc_now
from app.domain.entities.reader import Librarian, SystemAdmin
from app.domain.enums import ItemType
from app.domain.exceptions import NotFoundError


class QueryService:
    """查询应用服务。"""

    def __init__(
        self,
        readers: ReaderRepository,
        catalog: CatalogRepository,
        loans: LoanRepository,
        reservations: ReservationRepository,
        fines: FineRepository,
    ) -> None:
        self._readers = readers
        self._catalog = catalog
        self._loans = loans
        self._reservations = reservations
        self._fines = fines

    # ---- 查询图书（UC-003 / FR-014） ------------------------------------

    def search_books(
        self,
        keyword: str | None = None,
        item_type: ItemType | str | None = None,
        available_only: bool = False,
        page: int = 1,
        page_size: int = 20,
        include_deleted: bool = False,
    ) -> dict:
        """检索题录及其可借情况。已软删除的记录默认不出现（BR-037）。"""
        offset = max(page - 1, 0) * page_size
        titles = self._catalog.search_titles(
            keyword=keyword,
            item_type=ItemType(item_type) if item_type else None,
            available_only=available_only,
            include_deleted=include_deleted,
            offset=offset,
            limit=page_size,
        )
        return {
            "page": page,
            "page_size": page_size,
            "total": self._catalog.count_titles(
                keyword=keyword,
                item_type=ItemType(item_type) if item_type else None,
                available_only=available_only,
            ),
            "items": [
                {
                    "title_id": title.title_id,
                    "title": title.title,
                    "author": title.author,
                    "isbn": str(title.isbn) if title.isbn is not None else None,
                    "publisher": title.publisher,
                    "publish_year": title.publish_year,
                    "item_type": title.item_type.value if title.item_type else None,
                    "language": title.language,
                    "is_deleted": title.is_deleted,
                    "total_items": title.total_items(),
                    "available_items": len(title.available_items()),
                }
                for title in titles
            ],
        }

    # ---- 查询借阅信息（UC-004 / UC-103 / FR-019） -----------------------

    def get_reader_loans(
        self,
        reader_id: int,
        account,
        status_filter: str | None = None,
        now: datetime | None = None,
    ) -> dict:
        """返回四段结构：当前借阅、历史借阅、预约列表、罚款记录（FR-019 验收 1~4）。

        **归属校验**：读者只能查本人；馆员与管理员可查任意读者（BR-039）。
        **字段裁剪**：读者视角不返回经办管理员 ID（FR-019 验收 6）。
        """
        moment = now or utc_now()
        is_staff = isinstance(account, (Librarian, SystemAdmin))
        if not is_staff and getattr(account, "reader_id", None) != reader_id:
            raise ForbiddenError("只能查询本人的借阅信息")

        reader = self._readers.find_by_id(reader_id)
        if reader is None:
            raise NotFoundError("读者不存在", code="READER_NOT_FOUND")

        loans = list(self._loans.find_by_reader(reader_id))
        current, history, overdue = [], [], []
        item_cache = self._title_cache(loans)
        for loan in loans:
            entry = self._loan_entry(loan, item_cache, moment, include_operator=is_staff)
            if not loan.is_open():
                history.append(entry)
            elif loan.is_overdue(moment):
                overdue.append(entry)
                current.append(entry)
            else:
                current.append(entry)

        fines = list(self._fines.find_by_reader(reader_id))
        reservation_list = list(self._reservations.find_active_by_reader(reader_id))
        # 排队位置按题录分别计算：先取该读者各题录的有效队列
        queue_cache = {
            title_id: list(self._reservations.find_active_by_title(title_id))
            for title_id in {res.title_id for res in reservation_list}
        }

        result = {
            "reader": {
                "reader_id": reader.reader_id,
                "name": reader.name,
                "reader_type": reader.reader_type.value if reader.reader_type else None,
                "department": reader.department,
            },
            "current": current,
            "history": history,
            "overdue": overdue,
            "reservations": [
                {
                    "reservation_id": res.reservation_id,
                    "title_id": res.title_id,
                    "status": res.status.value,
                    "queue_position": res.queue_position(queue_cache.get(res.title_id, [])),
                    "ready_at": res.ready_at,
                }
                for res in reservation_list
            ],
            "fines": [
                {
                    "fine_id": fine.fine_id,
                    "amount": fine.amount.to_text(),
                    "status": fine.status.value,
                    "overdue_days": fine.overdue_days,
                    "billed_days": fine.billed_days,
                    "created_at": fine.created_at,
                    "paid_at": fine.paid_at,
                }
                for fine in fines
            ],
            "unpaid_total": self._fines.sum_unpaid_by_reader(reader_id),
        }

        if status_filter == "current":
            return {**result, "history": [], "overdue": []}
        if status_filter == "history":
            return {**result, "current": [], "overdue": []}
        if status_filter == "overdue":
            return {**result, "current": overdue, "history": []}
        return result

    # ---- 查询罚款（FR-026） ---------------------------------------------

    def get_reader_fines(self, reader_id: int, account) -> dict:
        is_staff = isinstance(account, (Librarian, SystemAdmin))
        if not is_staff and getattr(account, "reader_id", None) != reader_id:
            raise ForbiddenError("只能查询本人的罚款记录")

        records = list(self._fines.find_by_reader(reader_id))
        return {
            "unpaid": [
                self._fine_entry(record) for record in records if record.is_unpaid()
            ],
            "paid": [
                self._fine_entry(record) for record in records if not record.is_unpaid()
            ],
            "unpaid_total": self._fines.sum_unpaid_by_reader(reader_id),
        }

    # ---- 馆藏统计（FR-029 / UC-215） ------------------------------------

    def collection_stats(self) -> dict:
        return self._catalog.collection_stats()

    # ---- 覆盖统计（用于验证数据准备） -----------------------------------

    def count_active_loans(self, reader_id: int) -> int:
        return self._loans.count_active_by_reader(reader_id)

    # ---- 内部 ------------------------------------------------------------

    def _title_cache(self, loans) -> dict:
        cache: dict[int, object] = {}
        for loan in loans:
            if loan.item_id is None or loan.item_id in cache:
                continue
            item = self._catalog.find_item_by_id(loan.item_id)
            if item is None:
                continue
            title = self._catalog.find_title_by_id(item.title_id, with_items=False)
            cache[loan.item_id] = (item, title)
        return cache

    @staticmethod
    def _loan_entry(loan, item_cache: dict, now: datetime, include_operator: bool) -> dict:
        item, title = item_cache.get(loan.item_id, (None, None))
        entry = {
            "loan_id": loan.loan_id,
            "item_id": loan.item_id,
            "barcode": str(item.barcode) if item is not None else None,
            "title": title.title if title is not None else None,
            "borrowed_at": loan.borrowed_at,
            "due_at": loan.due_at,
            "returned_at": loan.returned_at,
            "status": loan.derived_status(now).value,
            "is_overdue": loan.is_overdue(now),
            "overdue_days": loan.overdue_days(now) if loan.is_open() else 0,
            "renew_count": loan.renew_count,
            "can_renew": loan.can_renew(now),
        }
        # FR-019 验收 6：读者视角不展示经办图书管理员 ID（内部审计字段）
        if include_operator:
            entry["librarian_id"] = loan.librarian_id
        return entry

    @staticmethod
    def _fine_entry(record) -> dict:
        return {
            "fine_id": record.fine_id,
            "loan_id": record.loan_id,
            "amount": record.amount.to_text(),
            "status": record.status.value,
            "overdue_days": record.overdue_days,
            "billed_days": record.billed_days,
            "unit_price": record.unit_price.to_text(),
            "created_at": record.created_at,
            "paid_at": record.paid_at,
        }
