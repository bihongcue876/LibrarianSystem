"""读者与账号实体（`05-domain-model.md` §2、`06-domain-class-diagram.md` 图 1）。

**纯 Python，零框架依赖**——不得出现 `sqlalchemy` 的 `Column()` 或 `__tablename__`
（ADR-05：ORM 模型与领域实体分离；包图规则 R-3）。

设计要点（06 §10.1、§10.2）：

- `Reader` 是**抽象类**，不可直接实例化。
- `StudentReader` / `TeacherReader` 覆写 `borrow_limit()` 与 `borrow_days()`，
  数值**全部委托给 `BorrowPolicy` 查询**——这是 Strategy 模式在领域侧的落点，
  不得在实体中硬编码 `5` / `30` 之类的数值。
- `Librarian` / `SystemAdmin` **不继承** `Reader`：它们没有借阅额度，
  套用继承会引入无用属性并违反里氏替换。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Sequence

from app.domain.enums import CardStatus, ReaderType

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查，避免运行时循环导入
    from app.domain.entities.borrow_card import BorrowCard
    from app.domain.entities.fine_record import FineRecord
    from app.domain.entities.loan import Loan
    from app.domain.entities.reservation import Reservation
    from app.domain.policies import BorrowPolicy


@dataclass
class Reader:
    """读者基类（抽象）。

    标识：`reader_id`。承载借阅资格与额度语义。
    """

    reader_id: int | None = None
    name: str = ""
    department: str = ""
    reader_type: ReaderType | None = None
    username: str = ""
    password_hash: str = ""
    is_deleted: bool = False

    IS_ABSTRACT = True
    ROLE = "READER"

    # ---- 模板方法：由子类覆写 --------------------------------------------

    def borrow_limit(self, policy: "BorrowPolicy") -> int:
        """最大借阅数量。**必须由子类实现**，数值取自策略对象。"""
        raise NotImplementedError("Reader 是抽象类，borrow_limit 必须由子类实现")

    def borrow_days(self, policy: "BorrowPolicy") -> int:
        """借阅期限（天）。**必须由子类实现**，数值取自策略对象。"""
        raise NotImplementedError("Reader 是抽象类，borrow_days 必须由子类实现")

    # ---- 通用行为 --------------------------------------------------------

    def occupies_quota(
        self,
        loans: Sequence["Loan"],
        reservations: Sequence["Reservation"],
    ) -> int:
        """已占用的借阅额度 = 未归还借阅数 + 有效预约数（BR-007）。"""
        loan_count = sum(1 for loan in loans if loan.status.is_open)
        reservation_count = sum(1 for res in reservations if res.status.is_effective)
        return loan_count + reservation_count

    def remaining_quota(
        self,
        loans: Sequence["Loan"],
        reservations: Sequence["Reservation"],
        policy: "BorrowPolicy",
    ) -> int:
        return max(self.borrow_limit(policy) - self.occupies_quota(loans, reservations), 0)

    def can_borrow(
        self,
        loans: Sequence["Loan"],
        reservations: Sequence["Reservation"],
        fines: Sequence["FineRecord"],
    ) -> bool:
        """读者**自身**是否满足借书条件。

        注意：这只是资格判定的一部分。完整的六项校验由
        `BorrowEligibilityService` 承担（它还负责借阅证、副本等自身之外的条件）。
        """
        if self.is_deleted:
            return False
        if any(loan.is_overdue() for loan in loans if loan.status.is_open):
            return False
        if any(fine.is_unpaid() for fine in fines):
            return False
        return True

    def is_valid(self) -> bool:
        return not self.is_deleted

    def __str__(self) -> str:  # pragma: no cover - 展示用
        return f"{type(self).__name__}(id={self.reader_id}, name={self.name})"


@dataclass
class StudentReader(Reader):
    """学生读者。额度与期限由 `student_type` 决定。"""

    student_type: ReaderType | None = None
    IS_ABSTRACT = False

    def borrow_limit(self, policy: "BorrowPolicy") -> int:
        return policy.limit_for(self.student_type)

    def borrow_days(self, policy: "BorrowPolicy") -> int:
        return policy.days_for(self.student_type)


@dataclass
class TeacherReader(Reader):
    """教师读者。额度最高（20 册 / 90 天），无 `student_type`。"""

    IS_ABSTRACT = False

    def borrow_limit(self, policy: "BorrowPolicy") -> int:
        return policy.limit_for(ReaderType.TEACHER)

    def borrow_days(self, policy: "BorrowPolicy") -> int:
        return policy.days_for(ReaderType.TEACHER)


@dataclass
class Librarian:
    """图书管理员。**不继承** `Reader`（06 §10.2）。

    可以代理读者办理借书、还书与收缴罚款（BR-040）。
    """

    librarian_id: int | None = None
    name: str = ""
    username: str = ""
    password_hash: str = ""
    is_deleted: bool = False

    ROLE = "LIBRARIAN"

    def can_borrow_for(self, card: "BorrowCard") -> bool:
        """是否可以代持该借阅证的读者办理借书。

        权限层面图书管理员具备该能力；借阅证本身的资格校验由
        `BorrowEligibilityService` 完成（职责分离）。
        """
        return not self.is_deleted

    def can_collect_fine(self, fine_record: "FineRecord") -> bool:
        """是否可以收缴该笔罚款（未缴清才可收缴）。"""
        return not self.is_deleted and fine_record.is_unpaid()

    def is_valid(self) -> bool:
        return not self.is_deleted

    @property
    def account_id(self) -> int | None:
        return self.librarian_id


@dataclass
class SystemAdmin:
    """系统管理员。拥有全部权限，且是**唯一**能看见已软删除记录的角色（BR-037）。"""

    admin_id: int | None = None
    name: str = ""
    username: str = ""
    password_hash: str = ""
    is_deleted: bool = False

    ROLE = "SYSTEM_ADMIN"

    # ---- 权限能力（供应用层查询，不承担持久化） --------------------------

    def may_manage_cards(self) -> bool:
        return not self.is_deleted

    def may_manage_accounts(self) -> bool:
        return not self.is_deleted

    def may_manage_catalog(self) -> bool:
        return not self.is_deleted

    def may_maintain_policy(self) -> bool:
        return not self.is_deleted

    # ---- 领域侧入口（06 图 1）-------------------------------------------

    def issue_card(self, reader: Reader, card_number) -> "BorrowCard":
        """签发借阅证。

        `card_number`（`CardNumber` 值对象）由调用方提供——序号来源属于
        基础设施关注点，领域层不负责取号。
        """
        from app.domain.entities.borrow_card import BorrowCard

        if not self.may_manage_cards():
            raise PermissionError("系统管理员账号不可用")
        return BorrowCard.issue(reader, self, card_number)

    def cancel_card(self, card: "BorrowCard") -> None:
        if not self.may_manage_cards():
            raise PermissionError("系统管理员账号不可用")
        card.cancel(self)

    def restore_card(self, card: "BorrowCard") -> None:
        if not self.may_manage_cards():
            raise PermissionError("系统管理员账号不可用")
        card.restore(self)

    def maintain_policy(self, policy: "BorrowPolicy", reader_type, max_count: int, days: int) -> None:
        if not self.may_maintain_policy():
            raise PermissionError("系统管理员账号不可用")
        policy.update(reader_type, max_count, days, operator=self)

    def is_valid(self) -> bool:
        return not self.is_deleted

    @property
    def account_id(self) -> int | None:
        return self.admin_id
