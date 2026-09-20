"""策略对象包（`05-domain-model.md` §8）。Strategy 模式的领域侧落点。"""

from app.domain.policies.borrow_policy import BorrowPolicy
from app.domain.policies.fine_rule import FineRule

__all__ = ["BorrowPolicy", "FineRule"]
