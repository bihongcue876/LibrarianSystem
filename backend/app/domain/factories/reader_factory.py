"""ReaderFactory（`05-domain-model.md` §1.2）。

按 `reader_type` 分派创建正确的 `Reader` 子类，
避免调用方（应用服务、Mapper）写 `if reader_type == "TEACHER"` 之类的分支。

**注意**：本类属于 `domain/factories/`，而 `domain/entities/` **不得**反向依赖它（包图规则 D-7）。
"""

from __future__ import annotations

from app.domain.entities.reader import Reader, StudentReader, TeacherReader
from app.domain.enums import ReaderType

STUDENT_TYPES = (
    ReaderType.COLLEGE,
    ReaderType.UNDERGRADUATE,
    ReaderType.GRADUATE,
    ReaderType.DOCTOR,
)


class ReaderFactory:
    """按读者类型创建 `Reader` 子类。"""

    @staticmethod
    def create(reader_type: ReaderType | str, **fields) -> Reader:
        """创建读者实体。

        `fields` 为实体属性（`reader_id`、`name`、`department`、`username`、
        `password_hash`、`is_deleted`）。
        """
        key = ReaderType(reader_type)
        if key is ReaderType.TEACHER:
            return TeacherReader(reader_type=key, **fields)
        return StudentReader(reader_type=key, student_type=key, **fields)

    @staticmethod
    def student_types() -> tuple[ReaderType, ...]:
        return STUDENT_TYPES
