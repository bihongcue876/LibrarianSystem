"""借阅规则策略单元测试（TASK-007 验收标准）。

**注意**：本文件中的 `5/30`、`10/60` 等数值是**测试期望值**（断言的目标），
不是生产代码里的规则分支——`app/domain/policies/` 中不得出现这些字面量。
"""

from __future__ import annotations

import pytest

from app.domain.entities.reader import StudentReader, TeacherReader
from app.domain.enums import ReaderType
from app.domain.exceptions import ValidationError
from app.domain.policies import BorrowPolicy

RULE_ROWS = [
    {"reader_type": "COLLEGE", "max_borrow_count": 5, "borrow_days": 30},
    {"reader_type": "UNDERGRADUATE", "max_borrow_count": 5, "borrow_days": 30},
    {"reader_type": "GRADUATE", "max_borrow_count": 10, "borrow_days": 60},
    {"reader_type": "DOCTOR", "max_borrow_count": 15, "borrow_days": 90},
    {"reader_type": "TEACHER", "max_borrow_count": 20, "borrow_days": 90},
]


@pytest.fixture()
def policy() -> BorrowPolicy:
    return BorrowPolicy.from_rows(RULE_ROWS)


@pytest.mark.parametrize(
    "reader_type,limit,days",
    [
        ("COLLEGE", 5, 30),
        ("UNDERGRADUATE", 5, 30),
        ("GRADUATE", 10, 60),
        ("DOCTOR", 15, 90),
        ("TEACHER", 20, 90),
    ],
)
def test_limit_and_days_per_type(policy, reader_type, limit, days):
    assert policy.limit_for(reader_type) == limit
    assert policy.days_for(reader_type) == days


def test_reader_entity_delegates_to_policy(policy):
    """实体不得硬编码额度——必须经策略对象查询。"""
    graduate = StudentReader(reader_id=1, reader_type=ReaderType.GRADUATE, student_type=ReaderType.GRADUATE)
    teacher = TeacherReader(reader_id=2, reader_type=ReaderType.TEACHER)

    assert graduate.borrow_limit(policy) == 10
    assert graduate.borrow_days(policy) == 60
    assert teacher.borrow_limit(policy) == 20
    assert teacher.borrow_days(policy) == 90


def test_update_changes_lookup(policy):
    policy.update("GRADUATE", 12, 45, operator=None)
    assert policy.limit_for("GRADUATE") == 12
    assert policy.days_for("GRADUATE") == 45


def test_update_rejects_invalid_values(policy):
    with pytest.raises(ValidationError):
        policy.update("GRADUATE", 0, 60)
    with pytest.raises(ValidationError):
        policy.update("GRADUATE", 10, 0)


def test_unknown_type_raises(policy):
    with pytest.raises(ValidationError):
        policy.limit_for("VISITING_SCHOLAR")


def test_abstract_reader_cannot_be_used():
    from app.domain.entities.reader import Reader

    reader = Reader(reader_id=1, reader_type=ReaderType.GRADUATE)
    with pytest.raises(NotImplementedError):
        reader.borrow_limit(BorrowPolicy.from_rows(RULE_ROWS))


def test_entries_exposes_all_rules(policy):
    assert len(policy.entries()) == 5
