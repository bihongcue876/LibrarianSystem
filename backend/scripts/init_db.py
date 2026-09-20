"""初始化脚本：建表 → 播种规则 → 创建首个系统管理员。

用法：

```bash
python scripts/init_db.py --admin-username admin --admin-name <姓名> --admin-password <密码>
```

**密码必须由命令行参数传入，无默认值**（决策：初始化密码不得硬编码，`13` §7.1）。
规则数值属于**数据**而非**代码**，故允许出现在本脚本中（BR-049）。
脚本幂等：重复执行只补齐缺失行，不会重复插入。

> 输出刻意使用 ASCII（`[OK]` / `[SKIP]` / `[FAIL]`）——Windows 控制台默认 GBK
> 编码，打印 `✓` 这类字符会直接抛 `UnicodeEncodeError` 导致脚本中断。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许以 `python scripts/init_db.py` 方式直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.infrastructure.db.base import Base  # noqa: E402
from app.infrastructure.db.session import SessionLocal, engine  # noqa: E402
from app.infrastructure.models import (  # noqa: E402
    BorrowPolicyModel,
    FineRuleModel,
    SystemAdminModel,
    load_all_models,
)
from app.infrastructure.security.password import hash_password  # noqa: E402

# ---------------------------------------------------------------------------
# 种子数据（决策 D-12、D-25、D-26）
# ---------------------------------------------------------------------------

BORROW_POLICY_SEED = [
    ("COLLEGE", 5, 30),
    ("UNDERGRADUATE", 5, 30),
    ("GRADUATE", 10, 60),
    ("DOCTOR", 15, 90),
    ("TEACHER", 20, 90),
]

FINE_RULE_SEED = [
    ("CHINESE_BOOK", "0.20", 2, "100.00"),
    ("FOREIGN_BOOK", "0.50", 2, "100.00"),
    ("CHINESE_MAGAZINE", "0.10", 2, "100.00"),
    ("FOREIGN_MAGAZINE", "0.20", 2, "100.00"),
    ("THESIS", "1.00", 2, "100.00"),
]


def create_tables() -> None:
    load_all_models()
    Base.metadata.create_all(bind=engine)
    print("[OK] tables ready (11 tables)")


def seed_policies(session) -> None:
    existing = {row.reader_type for row in session.scalars(select(BorrowPolicyModel)).all()}
    added = 0
    for reader_type, max_count, days in BORROW_POLICY_SEED:
        if reader_type in existing:
            continue
        session.add(
            BorrowPolicyModel(
                reader_type=reader_type, max_borrow_count=max_count, borrow_days=days
            )
        )
        added += 1
    print(f"[OK] borrow policies: {added} added, {len(existing)} skipped")

    existing_rules = {row.item_type for row in session.scalars(select(FineRuleModel)).all()}
    added = 0
    for item_type, price, grace, cap in FINE_RULE_SEED:
        if item_type in existing_rules:
            continue
        session.add(
            FineRuleModel(
                item_type=item_type, daily_price=price, grace_days=grace, max_amount=cap
            )
        )
        added += 1
    print(f"[OK] fine rules: {added} added, {len(existing_rules)} skipped")


def create_admin(session, username: str, name: str, password: str) -> None:
    if not password:
        raise SystemExit("[FAIL] --admin-password is required (no default value)")
    existing = session.scalar(
        select(SystemAdminModel).where(SystemAdminModel.username == username)
    )
    if existing is not None:
        print(f"[SKIP] system admin {username} already exists")
        return
    session.add(
        SystemAdminModel(name=name, username=username, password_hash=hash_password(password))
    )
    print(f"[OK] system admin created: {username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化图书管理系统数据库")
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--admin-name", default="System Admin")
    parser.add_argument(
        "--admin-password",
        required=True,
        help="首个系统管理员的密码（必填，无默认值）",
    )
    args = parser.parse_args()

    create_tables()
    session = SessionLocal()
    try:
        seed_policies(session)
        create_admin(session, args.admin_username, args.admin_name, args.admin_password)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print("[OK] database initialized")


if __name__ == "__main__":
    main()
