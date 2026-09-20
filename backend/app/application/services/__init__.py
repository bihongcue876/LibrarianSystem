"""应用服务包（Service Layer）。

**每个服务定义一个用例级的操作边界**，并**持有事务边界**（宪法第九条）。
服务只做「取数据 → 调领域对象 → 落库 → 组装结果」，不承载业务判定。
"""

from app.application.services.auth_service import AuthService
from app.application.services.card_service import CardService
from app.application.services.catalog_service import CatalogService
from app.application.services.circulation_service import CirculationService
from app.application.services.policy_service import PolicyService
from app.application.services.query_service import QueryService
from app.application.services.reservation_service import ReservationService

__all__ = [
    "AuthService",
    "CardService",
    "CatalogService",
    "CirculationService",
    "PolicyService",
    "QueryService",
    "ReservationService",
]
