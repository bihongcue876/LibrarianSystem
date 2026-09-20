"""工厂包（`05-domain-model.md` §1.2）。集中类型分派，避免应用服务里写 `if/elif`。"""

from app.domain.factories.library_item_factory import LibraryItemFactory
from app.domain.factories.reader_factory import ReaderFactory

__all__ = ["LibraryItemFactory", "ReaderFactory"]
