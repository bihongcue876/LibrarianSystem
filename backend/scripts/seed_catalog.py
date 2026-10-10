"""播种默认书目：从外部数据文件读取题录与副本，幂等写入内置数据库。

用法（在 `backend/` 下）：

```bash
uv run python scripts/seed_catalog.py                 # 使用默认数据文件
uv run python scripts/seed_catalog.py --data <路径>   # 指定数据文件
```

设计（决策 D-48、`13-database-design.md` §7）：

- 书目属于**数据**，放在外部 JSON 文件（`backend/data/default_catalog.json`），
  与代码分离；本脚本只负责把数据搬进库。
- 与 `init_db.py` **解耦**：`init_db.py` 只建表 + 规则 + 首个管理员，**不**含书目。
  需要默认藏书时另跑本脚本（可在 `init_db.py` 之后执行）。
- 幂等：同名活跃题录已存在则跳过；题录下已有副本则不再补副本。
- `created_by` 取库中首个系统管理员；若库中尚无管理员则置 NULL（该列可空）。

> 输出刻意使用 ASCII（`[OK]` / `[SKIP]` / `[FAIL]`），原因见 `init_db.py`。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# 允许以 `python scripts/seed_catalog.py` 方式直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.domain.value_objects.barcode import Barcode  # noqa: E402
from app.infrastructure.db.base import Base  # noqa: E402
from app.infrastructure.db.session import SessionLocal, engine  # noqa: E402
from app.infrastructure.models import (  # noqa: E402
    BookTitleModel,
    LibraryItemModel,
    SystemAdminModel,
    load_all_models,
)

DEFAULT_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "default_catalog.json"


def load_catalog(path: Path) -> tuple[list[dict], dict]:
    """读取书目数据文件，返回 `(题录列表, 默认值)`。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"[FAIL] cannot read data file {path}: {exc}") from exc
    titles = payload.get("titles")
    if not isinstance(titles, list):
        raise SystemExit("[FAIL] data file is missing the 'titles' list")
    defaults = payload.get("defaults") or {}
    return titles, defaults


def _next_barcode_sequence(session) -> int:
    """接续现有最大条码序号；空表返回 1（与仓储 `next_barcode_sequence` 一致）。"""
    current_max = session.scalar(select(func.max(LibraryItemModel.barcode)))
    if not current_max:
        return 1
    return int(str(current_max)[2:10]) + 1


def _first_admin_id(session) -> int | None:
    admin = session.scalar(
        select(SystemAdminModel)
        .where(SystemAdminModel.is_deleted == 0)
        .order_by(SystemAdminModel.admin_id.asc())
    )
    return admin.admin_id if admin is not None else None


def _create_tables() -> None:
    load_all_models()
    Base.metadata.create_all(bind=engine)


def seed_catalog(
    session, titles: list[dict], defaults: dict, admin_id: int | None
) -> tuple[int, int]:
    """写入题录与副本，返回 `(新增题录数, 新增副本数)`。"""
    next_sequence = _next_barcode_sequence(session)
    default_copies = int(defaults.get("copies", 1))
    default_acquired = defaults.get("acquired_at")
    titles_added = 0
    items_added = 0

    for entry in titles:
        name = entry.get("title")
        if not name:
            raise SystemExit("[FAIL] a title entry is missing the 'title' field")
        model = session.scalar(
            select(BookTitleModel).where(
                BookTitleModel.title == name,
                BookTitleModel.is_deleted == 0,
            )
        )
        if model is None:
            model = BookTitleModel(
                title=name,
                author=entry.get("author"),
                isbn=entry.get("isbn"),
                publisher=entry.get("publisher"),
                publish_year=entry.get("publish_year"),
                item_type=entry["item_type"],
                language=entry.get("language"),
                created_by=admin_id,
            )
            session.add(model)
            session.flush()
            titles_added += 1

        existing_items = session.scalar(
            select(func.count())
            .select_from(LibraryItemModel)
            .where(LibraryItemModel.title_id == model.title_id)
        )
        if existing_items:
            continue

        acquired_raw = entry.get("acquired_at", default_acquired)
        acquired_at = date.fromisoformat(acquired_raw) if acquired_raw else None
        copies = int(entry.get("copies", default_copies))
        for index in range(copies):
            session.add(
                LibraryItemModel(
                    barcode=str(Barcode.generate(next_sequence)),
                    title_id=model.title_id,
                    item_type=entry["item_type"],
                    status="AVAILABLE",
                    location=f"A-{model.title_id:02d}-{index + 1:02d}",
                    acquired_at=acquired_at,
                    price=entry.get("price"),
                    created_by=admin_id,
                )
            )
            next_sequence += 1
            items_added += 1

    return titles_added, items_added


def main() -> None:
    parser = argparse.ArgumentParser(description="把默认书目数据写入内置数据库")
    parser.add_argument(
        "--data",
        default=str(DEFAULT_DATA_FILE),
        help="书目数据文件（JSON），默认 backend/data/default_catalog.json",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.is_file():
        raise SystemExit(f"[FAIL] data file not found: {data_path}")
    titles, defaults = load_catalog(data_path)

    _create_tables()
    session = SessionLocal()
    try:
        admin_id = _first_admin_id(session)
        if admin_id is None:
            print("[WARN] no system admin found; created_by will be NULL")
        titles_added, items_added = seed_catalog(session, titles, defaults, admin_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print(f"[OK] book titles: {titles_added} added")
    print(f"[OK] library items: {items_added} added")
    print("[OK] catalog seeded")


if __name__ == "__main__":
    main()
