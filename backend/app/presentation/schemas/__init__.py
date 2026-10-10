"""Pydantic DTO 包（表现层）。

**DTD 的职责**：隔离 ORM 模型与 API 契约——**禁止直传 ORM 模型**（宪法第六条）。
"""

from app.presentation.schemas.auth_schemas import (
    AccountResponse,
    AddLibrarianRequest,
    LoginRequest,
    RegisterReaderRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.presentation.schemas.card_schemas import (
    BorrowCardResponse,
    IssueCardRequest,
)
from app.presentation.schemas.catalog_schemas import (
    AddBookTitleRequest,
    AddLibraryItemRequest,
    BookTitleResponse,
    LibraryItemResponse,
    MarkItemStatusRequest,
)
from app.presentation.schemas.circulation_schemas import (
    BorrowBookRequest,
    BorrowBookResponse,
    CollectFineResponse,
    PreCheckRequest,
    PreCheckResponse,
    RenewResponse,
    ReturnBookRequest,
    ReturnBookResponse,
)
from app.presentation.schemas.policy_schemas import (
    PoliciesResponse,
    UpdateBorrowPolicyRequest,
    UpdateFineRuleRequest,
)
from app.presentation.schemas.query_schemas import (
    BookListResponse,
    CollectionStatsResponse,
    ReaderFinesResponse,
    ReaderLoansResponse,
)
from app.presentation.schemas.reservation_schemas import (
    CancelReservationResponse,
    CreateReservationRequest,
    ReservationResponse,
)

__all__ = [
    "AccountResponse",
    "AddBookTitleRequest",
    "AddLibrarianRequest",
    "AddLibraryItemRequest",
    "BookListResponse",
    "BookTitleResponse",
    "BorrowBookRequest",
    "BorrowBookResponse",
    "BorrowCardResponse",
    "CancelReservationResponse",
    "CollectFineResponse",
    "CollectionStatsResponse",
    "CreateReservationRequest",
    "IssueCardRequest",
    "LibraryItemResponse",
    "LoginRequest",
    "MarkItemStatusRequest",
    "PoliciesResponse",
    "PreCheckRequest",
    "PreCheckResponse",
    "ReaderFinesResponse",
    "ReaderLoansResponse",
    "RegisterReaderRequest",
    "RenewResponse",
    "ReservationResponse",
    "ResetPasswordRequest",
    "ReturnBookRequest",
    "ReturnBookResponse",
    "TokenResponse",
    "UpdateBorrowPolicyRequest",
    "UpdateFineRuleRequest",
]
