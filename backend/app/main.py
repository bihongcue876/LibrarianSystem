"""应用入口：创建 FastAPI 实例、注册路由、注册全局异常处理器、配置 CORS。

异常 → HTTP 的统一映射在此完成（`07-architecture.md` §6.2、`09-design-model.md` §10）。

**注意状态码**：`02-requirements.md` 的各 FR 验收标准是**权威来源**。
例如 FR-016 规定借书的业务规则失败返回 **400**（而非通用表里的 409），
因此领域异常构造时已显式携带 `http_status`，本文件按异常自带的 `http_status` 映射。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.application.exceptions import ApplicationError
from app.domain.exceptions import DomainError
from app.presentation.routers import ALL_ROUTERS

app = FastAPI(
    title="AI时代图书管理系统",
    description="《软件设计与体系结构》实验二 —— Python + FastAPI 实现（分层架构）",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # 白名单：前端开发服务器（Vite 默认 5173）。凭据模式要求显式来源，
    # 通配符 `*` 与 `allow_credentials=True` 组合会被浏览器拒绝。
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    """健康检查（TASK-001 验收标准）。"""
    return {"status": "ok", "service": "library-management-system", "version": app.version}


# ---------------------------------------------------------------------------
# 统一异常处理
# ---------------------------------------------------------------------------

def _error_body(code: str, message: str, detail: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail or {}}}


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """领域异常 → HTTP。状态码取自异常自身（由 FR 决定）。"""
    return JSONResponse(
        status_code=exc.http_status,
        content=_error_body(exc.code, exc.message, exc.detail),
    )


@app.exception_handler(ApplicationError)
async def handle_application_error(request: Request, exc: ApplicationError) -> JSONResponse:
    """应用异常（401 / 403）→ HTTP。"""
    return JSONResponse(
        status_code=exc.http_status,
        content=_error_body(exc.code, exc.message, exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """请求体/查询参数校验失败 → 422（与 `14-api-spec.md` §1.3 一致）。

    只回显 `loc` / `msg` / `type` 摘要——pydantic 的原始错误项会携带
    用户输入原文（`input`）与内部模型路径（`url`），原样返回会泄露内部结构。
    """
    sanitized = [
        {"loc": item.get("loc"), "msg": item.get("msg"), "type": item.get("type")}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_body(
            "INVALID_PARAMETER", "请求参数校验失败", {"errors": sanitized}
        ),
    )


@app.exception_handler(PermissionError)
async def handle_permission_error(request: Request, exc: PermissionError) -> JSONResponse:
    """领域实体内部抛出的 `PermissionError` → 403。"""
    return JSONResponse(status_code=403, content=_error_body("PERMISSION_DENIED", str(exc)))


# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------

for router in ALL_ROUTERS:
    app.include_router(router)
