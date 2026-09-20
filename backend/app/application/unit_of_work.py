"""事务边界抽象（`07-architecture.md` §6.3、宪法第九条）。

**事务边界只在应用服务层**。实现形态采用方案 A（显式事务上下文）：

```python
with self._uow:
    ...
    self._uow.commit()
```

Repository 只负责读写，**不提交事务**——提交权收归应用服务。
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session


class UnitOfWork:
    """基于 SQLAlchemy Session 的显式事务边界。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._committed = False

    @property
    def session(self) -> Session:
        return self._session

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        """异常时回滚；正常退出但未显式提交时也回滚（避免半成品事务泄露）。"""
        if exc_type is not None:
            self.rollback()
            return False
        if not self._committed:
            self.rollback()
        return False

    def commit(self) -> None:
        self._session.commit()
        self._committed = True

    def rollback(self) -> None:
        self._session.rollback()
        self._committed = False

    def flush(self) -> None:
        """把挂起变更刷入事务（用于需要拿到自增主键的场景），**不提交**。"""
        self._session.flush()
