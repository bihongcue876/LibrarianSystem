"""读者类型枚举（`05-domain-model.md` §2.1）。"""

from __future__ import annotations

from enum import Enum


class ReaderType(str, Enum):
    COLLEGE = "COLLEGE"                    # 专科生
    UNDERGRADUATE = "UNDERGRADUATE"        # 本科生
    GRADUATE = "GRADUATE"                  # 研究生
    DOCTOR = "DOCTOR"                      # 博士生
    TEACHER = "TEACHER"                    # 教师

    @property
    def is_student(self) -> bool:
        return self is not ReaderType.TEACHER
