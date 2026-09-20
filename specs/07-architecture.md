# 架构设计（Architecture Design）

> **文档编号**：`specs/07-architecture.md`
> **制定依据**：`constitution.md`（尤其第五、六、八、九条）、`02-requirements.md`、`05-domain-model.md`
> **版本**：v1.0
> **日期**：2026-09-19
>
> 本文件定义系统的**整体架构**：分层划分、依赖方向、技术选型、横切关注点、关键流程的落点，以及架构决策记录（ADR）。
>
> **约束来源**：本文件的所有架构决策必须与 `constitution.md` 一致。若冲突，以宪法为准。

---

## 1. 架构目标与约束

### 1.1 架构目标

| 目标 | 说明 | 对应需求 |
|---|---|---|
| **业务规则可维护** | 借阅规则与罚款规则存库可配，改规则不改代码 | FR-027、FR-028、BR-049 |
| **规则差异可扩展** | 新增读者类型或借出物类型时不改动核心流程 | BR-006、BR-028 |
| **职责边界清晰** | 路由不含业务规则，领域层不依赖框架 | 宪法第五、六条 |
| **可测试** | 规则计算与资格判定可脱离数据库与 HTTP 单测 | 宪法第十条 |
| **数据一致性可保证** | 五个关键操作有明确事务边界 | 宪法第九条、D-46c |
| **教学可解释** | 架构复杂度可控，每种设计模式的使用位置有据可查 | 实验文档教学要求 |

### 1.2 架构约束（硬性）

来自 `constitution.md`，不可协商：

| 编号 | 约束 |
|---|---|
| C-1 | 四层分层，依赖**单向向下** |
| C-2 | 领域层**不得**引用 FastAPI、SQLAlchemy 等框架 |
| C-3 | Router 函数只做四件事：接收请求、调用应用服务、捕获异常、返回响应 |
| C-4 | 请求/响应体必须经 Pydantic Schema（DTO），禁止直传 ORM 模型或领域实体 |
| C-5 | 权限校验在服务端，不得仅靠前端隐藏 |
| C-6 | 规则数值必须从数据库读取，**严禁**硬编码 |
| C-7 | 事务边界由应用服务层控制，不得在 Router 中开事务 |
| C-8 | 时间统一存 UTC，API 传 ISO 8601 带时区 |

### 1.3 明确不做（架构层面）

依据 `00-project-brief.md` §9 与宪法第十六条：

- 不做微服务拆分 —— 单体分层足够，微服务会带来分布式事务与部署复杂度
- 不做 CQRS / 事件溯源 —— 无读写分离压力，引入会显著抬高教学复杂度
- 不做 Repository 泛型基类的过度抽象 —— 按聚合根的实际需要定义接口
- 不做多租户、缓存层、消息队列 —— 无对应需求

---

## 2. 分层架构

### 2.1 四层职责

```
┌──────────────────────────────────────────────────────────────┐
│  表现层 Presentation                                          │
│  FastAPI Routers + Pydantic Schemas                          │
│  职责：HTTP 解析、参数校验、调用应用服务、异常转 HTTP 响应      │
│  依赖：→ 应用服务层                                            │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  应用服务层 Application                                        │
│  Services（CirculationService / CardService / ...）            │
│  职责：组织用例流程、控制事务边界、权限与归属校验、DTO ↔ 领域转换 │
│  依赖：→ 领域层、→ 基础设施层接口（Repository 接口）             │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  领域层 Domain                                                │
│  Entities / Value Objects / Domain Services / Policies        │
│  职责：业务规则、状态流转、金额计算、资格判定                    │
│  依赖：无（纯 Python，不 import 任何框架）                      │
└──────────────────────────────────────────────────────────────┘
                              ↑
                    实现接口（依赖倒置）
                              │
┌──────────────────────────────────────────────────────────────┐
│  基础设施层 Infrastructure                                     │
│  SQLAlchemy Models / Repository 实现 / JWT / 密码哈希 / 数据库  │
│  职责：持久化、ORM 映射、外部技术能力实现                        │
│  依赖：实现领域层或应用层定义的接口                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 各层详细职责

#### 2.2.1 表现层（presentation）

| 项 | 内容 |
|---|---|
| **技术** | FastAPI `APIRouter`、Pydantic `BaseModel` |
| **组成** | `routers/`（路由模块）、`schemas/`（DTO 定义） |
| **允许做** | 解析请求、Pydantic 参数校验、调用应用服务、捕获业务异常转 HTTP、返回响应 |
| **禁止做** | 业务条件判断、数据库查询、金额计算、状态变更、直接操作 ORM |
| **错误处理** | 通过 FastAPI `exception_handler` 统一将领域异常映射为 HTTP 状态码 |

**Router 函数的形态约束（宪法第六条）**：

```python
@router.post("/borrow", response_model=BorrowBookResponse)
def borrow_book(
    req: BorrowBookRequest,
    svc: CirculationService = Depends(get_circulation_service),
    current: Account = Depends(require_role(Role.LIBRARIAN)),
) -> BorrowBookResponse:
    return svc.borrow_book(req, operator=current)
```

一个 Router 函数的**典型体量是 1-3 行**。若超过 10 行，说明业务逻辑漏到了表现层。

#### 2.2.2 应用服务层（application）

| 项 | 内容 |
|---|---|
| **技术** | 纯 Python 类，依赖通过构造函数注入 |
| **组成** | `services/`（应用服务） |
| **职责** | ① 组织用例流程（编排多个领域对象与领域服务）；② **控制事务边界**；③ 权限与资源归属校验；④ DTO ↔ 领域对象转换；⑤ 记录审计字段（操作人） |
| **禁止做** | 承载可直接放入领域的业务规则（如"5 册上限"）、直接写 SQL |

**应用服务清单**（对应 8 个功能模块）：

| 应用服务 | 覆盖用例 | 主要事务 |
|---|---|---|
| `AuthService` | UC-001、UC-002 | 注册、登录 |
| `CardService` | UC-201 ~ UC-205、UC-206a | 办证、注销、恢复、挂失、解挂 |
| `CatalogService` | UC-207 ~ UC-212 | 题录增改删、副本增改删 |
| `CirculationService` | UC-101、UC-102、UC-102a、UC-103、UC-104、UC-007 | **借书、还书、续借、收缴罚款** |
| `ReservationService` | UC-005、UC-006 | 预约、取消预约 |
| `QueryService` | UC-003、UC-004、UC-008、UC-215 | 查询与统计（只读，无事务） |
| `PolicyService` | UC-213、UC-214 | 规则维护 |

> **命名冲突提示**：领域层有一个 `RenewalService`（领域服务），应用层有 `CirculationService.renew()`（应用方法）。两者职责不同——领域服务判定"能不能续"，应用服务负责"取数据 → 调领域服务 → 落库 → 提交事务"。数据库设计时必须区分。

#### 2.2.3 领域层（domain）

| 项 | 内容 |
|---|---|
| **技术** | 纯 Python（可用 `dataclasses`、`decimal`、`enum`、`datetime`） |
| **组成** | `entities/`、`value_objects/`、`domain_services/`、`policies/` |
| **职责** | 承载全部业务规则与状态流转 |
| **禁止做** | `import fastapi`、`import sqlalchemy`、读写环境变量、发起网络请求 |

**领域层内容一览**（详见 `05-domain-model.md`）：

| 子包 | 内容 |
|---|---|
| `entities/` | `Reader`、`StudentReader`、`TeacherReader`、`Librarian`、`SystemAdmin`、`BorrowCard`、`BookTitle`、`LibraryItem`、`Book`、`Magazine`、`Thesis`、`Loan`、`Reservation`、`FineRecord` |
| `value_objects/` | `CardNumber`、`Barcode`、`Isbn`、`Money`、`DateRange` |
| `enums/` | `ReaderType`、`ItemType`、`ItemStatus`、`CardStatus`、`LoanStatus`、`ReservationStatus`、`FineStatus` |
| `domain_services/` | `BorrowEligibilityService`、`RenewalService`、`ReservationQueueService` |
| `policies/` | `BorrowPolicy`、`FineRule` |

**领域层纯净性的检验方法**：删掉 `fastapi` 与 `sqlalchemy` 后，`domain/` 目录下的代码应当仍能**独立导入并运行单元测试**。这是可机械验证的标准。

#### 2.2.4 基础设施层（infrastructure）

| 项 | 内容 |
|---|---|
| **技术** | SQLAlchemy 2.x ORM、SQLite、`passlib[bcrypt]` 或 `bcrypt`、`python-jose` 或 `PyJWT` |
| **组成** | `db/`（会话、基类）、`models/`（ORM 映射）、`repositories/`（接口实现）、`security/`（JWT、密码） |
| **职责** | ① ORM 映射与持久化；② Repository 接口实现；③ JWT 签发与校验；④ 密码哈希 |
| **禁止做** | 包含业务规则（如判断是否超期） |

### 2.3 依赖方向与依赖倒置

```
presentation  ──→  application  ──→  domain  ←──  infrastructure
     （单向向下）              （接口定义）  （接口实现，方向反转）
```

**关键机制**：Repository 接口定义在**应用服务层或领域层**，实现放在基础设施层。

```python
# application/ports/loan_repository.py  —— 接口（属于应用层）
class LoanRepository(Protocol):
    def find_active_by_reader(self, reader_id: int) -> list[Loan]: ...
    def find_by_item(self, item_id: int) -> Loan | None: ...
    def save(self, loan: Loan) -> None: ...

# infrastructure/repositories/sqlalchemy_loan_repository.py —— 实现
class SqlAlchemyLoanRepository(LoanRepository):
    def __init__(self, session: Session) -> None:
        self._session = session
    ...
```

**收益**：

- 应用服务的单元测试可注入内存假实现，不依赖数据库
- 领域对象不感知持久化方式

**注意接口归属的取舍**：Repository 接口放在**应用层**（而非领域层），因为本项目的领域模型是**充血但非持久化透明**的——实体不需要知道如何自救。这比"领域层定义 Repository"更简单，且同样满足依赖倒置。

### 2.4 依赖规则的可执行检查

| 检查项 | 检查方式 |
|---|---|
| 领域层不含框架导入 | 在 `domain/` 下 grep `fastapi`、`sqlalchemy` → 必须 0 命中 |
| Router 不含业务规则 | 人工审查 + Router 函数行数应 ≤ 10 行 |
| 无跨层反向依赖 | 检查 `infrastructure/` 不 import `presentation/` |
| DTO 未泄漏 ORM 模型 | 检查 `schemas/` 不 import `infrastructure/models/` |

---

## 3. MVC 在 FastAPI 中的映射

### 3.1 映射关系

| MVC 角色 | 本项目对应 | 说明 |
|---|---|---|
| **Model** | 领域实体 + 值对象 + ORM 模型 | 领域模型是面向业务的 Model，ORM 模型是持久化映射 |
| **View** | Pydantic Response Schema（JSON） | 本项目为前后端分离，View 是 JSON 序列化结果，非 HTML 模板 |
| **Controller** | FastAPI `APIRouter` 函数 | 只做请求转发 |

### 3.2 一个请求的完整流经路径

以「办理借书」（UC-101）为例：

```
①  HTTP POST /api/circulation/borrow
        │
②  presentation/routers/circulation_router.py
    ├─ Pydantic 校验请求体（BorrowBookRequest）
    ├─ 依赖注入：require_role(LIBRARIAN) 校验角色，取当前操作人
    └─ 调用 svc.borrow_book(req, operator=current)
        │
③  application/services/circulation_service.py :: borrow_book()
    ├─ 开启事务
    ├─ 经 Repository 加载：BorrowCard、Reader、Loan[]、Reservation[]、FineRecord[]、LibraryItem、BorrowPolicy
    ├─ 调 BorrowEligibilityService.check_eligibility(...)   ← 领域层判定
    │     └─ 校验顺序：权限 → 借阅证 → 数量 → 超期 → 罚款 → 副本
    ├─ 通过则：Loan.create(...) 创建借阅记录（领域层，快照 due_at）
    ├─ item.mark_borrowed() 变更副本状态（领域层）
    ├─ 经 Repository 落库
    └─ 提交事务 / 失败回滚
        │
④  返回 BorrowBookResponse（Pydantic Schema）
```

**关键分工**：

| 环节 | 归属层 | 为什么 |
|---|---|---|
| 参数格式校验 | 表现层（Pydantic） | 是接口契约问题，非业务问题 |
| 角色权限校验 | 应用层（依赖注入守卫） | 需读取当前登录身份 |
| 借阅资格判定 | 领域层（`BorrowEligibilityService`） | 是业务规则，纯判定无副作用 |
| 状态变更 | 领域层（实体方法） | 由实体守护自身不变量 |
| 事务提交 | 应用层 | 需感知操作边界 |
| 落库 | 基础设施层 | 技术实现 |

### 3.3 禁止事项示例

```python
# ❌ 严禁：业务规则写入 Router（违反宪法第六条）
@router.post("/borrow")
def borrow(req: BorrowRequest, db: Session = Depends(get_db)):
    card = db.query(BorrowCardModel).filter_by(card_no=req.card_no).first()
    if not card or card.status != "ACTIVE":      # 业务规则！
        raise HTTPException(400, "借阅证无效")
    count = db.query(LoanModel).filter_by(reader_id=card.reader_id).count()
    if count >= 5:                               # 硬编码额度！
        raise HTTPException(400, "超出借阅数量")
```

```python
# ✅ 正确：Router 只做转发
@router.post("/borrow", response_model=BorrowBookResponse)
def borrow_book(
    req: BorrowBookRequest,
    svc: CirculationService = Depends(get_circulation_service),
    current: Account = Depends(require_role(Role.LIBRARIAN)),
) -> BorrowBookResponse:
    return svc.borrow_book(req, operator=current)
```

---

## 4. 设计模式使用位置

> 宪法第八条规定了推荐的模式位置，此处展开说明**为什么**。

| 模式 | 使用位置 | 解决的问题 | 对应代码 |
|---|---|---|---|
| **Strategy** | 领域层 `policies/` | 读者类型差异（5/5/10/15/20 册）与借出物类型差异（0.10~1.00 元/天）若用 `if/else` 会导致新增类型需改核心流程 | `BorrowPolicy`、`FineRule` |
| **Repository** | 应用层定义接口，基础设施层实现 | 隔离 ORM，使应用服务可单测；领域对象不感知持久化 | `LoanRepository` 等 |
| **Service Layer** | 应用层 | 组织用例流程、控制事务边界，使 Router 保持极薄 | `CirculationService` 等 |
| **DTO** | 表现层 `schemas/` | 隔离接口契约与领域模型；防止领域实体字段变更直接破坏 API 契约 | `BorrowBookRequest` / `BorrowBookResponse` |
| **Factory** | 领域层 | 按 `ReaderType` / `ItemType` 创建具体子类，避免调用方写分支 | `ReaderFactory`、`LibraryItemFactory` |
| **MVC** | 表现层 | 分离路由、服务与模型 | Routers / Services / Models |

### 4.1 Strategy 模式的具体形态

本系统的策略**不是**"多个可互换的算法类"，而是**"查表型策略"**——差异体现在数据表而非代码分支：

```python
# ✅ 正确：查表
class BorrowPolicy:
    def limit_for(self, reader_type: ReaderType) -> int:
        row = self._repo.find_by_reader_type(reader_type)   # 查数据库
        return row.max_borrow_count

# ❌ 严禁：硬编码分支（违反宪法第八条）
def limit_for(self, reader_type: str) -> int:
    if reader_type == "UNDERGRADUATE":
        return 5
    elif reader_type == "GRADUATE":
        return 10
    ...
```

**理由**：实验要求实现「维护借阅规则和罚款规则」用例（UC-213/UC-214）。若规则写死在代码中，该用例**无法真实实现**——改规则需要改代码、重启、重新部署。因此规则必须存数据库（BR-049，决策 D-47a）。

### 4.2 Factory 模式的边界

Factory 仅用于**创建时的类型分派**，不承担其他职责：

```python
class ReaderFactory:
    @staticmethod
    def create(reader_type: ReaderType, **kwargs) -> Reader:
        match reader_type:
            case ReaderType.COLLEGE | ReaderType.UNDERGRADUATE \
               | ReaderType.GRADUATE | ReaderType.DOCTOR:
                return StudentReader(**kwargs)
            case ReaderType.TEACHER:
                return TeacherReader(**kwargs)
```

**这个 `match` 是允许的**——它分派的是**类型创建**，而非**规则数值**。规则数值仍在数据库。

---

## 5. 技术选型

### 5.1 技术栈

| 层 | 技术 | 版本 | 选型理由 |
|---|---|---|---|
| 表现层 | FastAPI | ≥ 0.110 | 原生异步、Pydantic 集成、自动 OpenAPI 文档 |
| 表现层 | Pydantic | ≥ 2.x | 参数校验与 DTO 定义，性能优于 v1 |
| 应用层 | 纯 Python | 3.11+ | 用 `match` 语法、`Protocol`、`dataclass` |
| 领域层 | 纯 Python | 3.11+ | 同上，零框架依赖 |
| 基础设施 | SQLAlchemy | ≥ 2.x | ORM 映射，2.0 风格支持类型标注 |
| 基础设施 | SQLite | 内置 | 零部署成本，满足课程实验规模；通过 SQLAlchemy 隔离，后续可换 PostgreSQL |
| 基础设施 | passlib + bcrypt | — | 密码哈希（BR-045） |
| 基础设施 | PyJWT | — | 简化版 JWT 登录（D-01、D-01a） |
| 测试 | pytest | ≥ 8.x | 单元测试 + 集成测试 |
| 测试 | httpx / `TestClient` | — | 端到端 API 测试 |
| 前端 | TypeScript（+ HTML/CSS） | 5.x | 实验二交付；实验一不涉及代码 |

### 5.2 Python 版本要求

要求 **Python 3.11+**，原因：

- `match` 语句（Factory 模式实现）
- `typing.Protocol`（Repository 接口）
- `datetime.UTC` 常量（时间处理）
- PEP 604 联合类型语法 `int | None`

### 5.3 数据库选型说明

选 **SQLite** 的理由与代价：

| 方面 | 说明 |
|---|---|
| **优点** | 零部署、单文件、便于提交与演示、pytest 可用内存库 |
| **代价** | 无真正的行级锁；并发写会串行化 |
| **缓解** | 本项目为课程规模，无并发压力；事务仍通过 SQLAlchemy `Session` 显式控制 |
| **可迁移性** | 通过 Repository 接口隔离，更换为 PostgreSQL 只需替换实现层 |

---

## 6. 横切关注点

### 6.1 认证与鉴权

**方案**：简化版 JWT（决策 D-01、D-01a）

| 项 | 设计 |
|---|---|
| 认证方式 | `POST /api/auth/login` 返回 JWT |
| Token 有效期 | 24 小时，**无 refresh token**（简化） |
| 密码存储 | bcrypt 哈希（BR-045） |
| 密码规则 | 长度 6-24 位 |
| 用户名规则 | 长度 3-32 位，仅字母/数字/下划线 |
| 传输方式 | `Authorization: Bearer <token>` |

**JWT Payload 设计**：

```json
{
  "sub": "42",
  "role": "READER",
  "exp": 1726812345,
  "iat": 1726725945
}
```

**鉴权守卫（依赖注入）**：

```python
def require_role(*allowed: Role):
    def guard(current: Account = Depends(get_current_account)) -> Account:
        if current.role not in allowed:
            raise ForbiddenError()
        return current
    return guard
```

**资源归属校验**（宪法第七条）：读者查询自己数据时，服务端**不得**信任请求参数中的 `reader_id`，必须用 token 中的 `sub`：

```python
# ❌ 错误：直接信任路径参数
@router.get("/readers/{reader_id}/loans")
def list_loans(reader_id: int, ...): ...

# ✅ 正确：从 token 取 reader_id
@router.get("/me/loans")
def list_my_loans(current: Account = Depends(require_role(Role.READER))): ...
```

**权限矩阵**（以 `01-clarifying-questions.md` D-05 为准）：

| 功能域 | 读者 READER | 图书管理员 LIBRARIAN | 管理员 ADMIN |
|---|:---:|:---:|:---:|
| 查询自己的借阅/预约/罚款 | ✅ | — | — |
| 查询任意读者信息 | ❌ | ✅ | ✅ |
| 办理借书 / 还书 / 续借 | ❌ | ✅ | ❌ |
| 收缴罚款 | ❌ | ✅ | ❌ |
| 预约 / 取消预约 | ✅ | ❌ | ❌ |
| 借阅证管理 | ❌ | ❌ | ✅ |
| 账号管理 | ❌ | ❌ | ✅ |
| 书目与馆藏管理 | ❌ | ❌ | ✅ |
| 规则维护 | ❌ | ❌ | ✅ |
| 查询已软删除记录 | ❌ | ❌ | ✅ |

### 6.2 异常处理

**统一异常体系**：领域层抛业务异常，表现层统一映射为 HTTP 响应。

| 异常类 | 归属层 | HTTP 状态码 | 场景示例 |
|---|---|---|---|
| `NotFoundError` | 领域 | 404 | 馆藏条码不存在、借阅记录不存在 |
| `ValidationError` | 领域 | 400 | 借阅证状态非 `ACTIVE`、参数格式错误 |
| `BusinessRuleError` | 领域 | 409 | 超出借阅额度、有超期未还、队列已满 |
| `ForbiddenError` | 应用 | 403 | 角色无权、读者访问他人数据 |
| `UnauthorizedError` | 应用 | 401 | 未登录、token 过期 |
| `ConflictError` | 领域 | 409 | 重复预约、重复办证 |

**统一响应体**：

```json
{
  "error": {
    "code": "BORROW_LIMIT_EXCEEDED",
    "message": "超出借阅数量上限",
    "detail": { "current": 5, "limit": 5 }
  }
}
```

**全局异常处理器**（表现层）：

```python
@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content={"error": {...}})
```

**借书校验顺序决定错误码**（对应 `03-use-cases.md` UC-101 固定顺序）：权限 → 借阅证 → 数量 → 超期 → 罚款 → 副本。**遇到第一个失败即返回**，不累积错误。

> **本表与具体 FR 的关系**：上表是**层级的通用映射约定**（哪个异常类大致对应哪个状态段）。**具体接口的状态码与错误码以 `02-requirements.md` 各 FR 的验收标准为准**——例如 FR-016 把借书的多项业务规则失败规定为 **400**（而非本表的 409），`14-api-spec.md` 已按 FR 校准。两者冲突时**以 FR 为准**。

### 6.3 事务管理

事务边界**只在应用服务层**（宪法第九条、C-7）。

| 操作 | 事务范围 | 提交点 |
|---|---|---|
| 办理借书 | 校验额度 → 创建 `Loan` → 更新 `LibraryItem` 状态 | 全部成功后 |
| 办理还书 | 更新 `Loan` → 更新 `LibraryItem` → 生成 `FineRecord` → 处理预约预留 | 全部成功后 |
| 预约图书 | 校验队列 → 创建 `Reservation` | 成功后 |
| 办理借阅证 | 校验读者 → 生成证号 → 创建 `BorrowCard` | 成功后 |
| 续借 | 校验次数 → 更新 `due_at` → 递增续借次数 | 成功后 |

**实现形态**（二选一，推荐 A）：

```python
# 方案 A：显式事务上下文（推荐，边界清晰可见）
class CirculationService:
    def borrow_book(self, req: BorrowBookRequest, operator: Account) -> BorrowBookResponse:
        with self._uow:                       # Unit of Work 上下文管理器
            ...                               # 全部领域操作
            self._uow.commit()                # 显式提交
        return response

# 方案 B：FastAPI 依赖注入的会话生命周期
async def get_circulation_service(session = Depends(get_session)) -> CirculationService:
    try:
        yield CirculationService(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
```

**并发控制**：本项目采**悲观程度最低的方案**——依赖 SQLite 的写串行化 + 事务原子性。预约队列的并发安全由应用层事务保证（`05-domain-model.md` §6.3 已注明）。**不引入**乐观锁版本号，理由见 §10.3。

### 6.4 日志与审计

**审计要求**（决策 D-46g）：10 类写操作均需记录操作人。

| 审计方式 | 说明 |
|---|---|
| **业务字段留存** | 实体自带操作人字段：`Loan.librarian_id`、`BorrowCard.issued_by`、`FineRecord.operator_id`、`BorrowPolicy.updated_by` |
| **时间戳留存** | `created_at` / `updated_at` / `issued_at` / `paid_at` 等 |

**设计取舍**：本项目**不做独立的审计日志表**，而是把操作人作为**业务字段**留在各实体上。

**理由**：

1. 实验要求的审计粒度是"谁办了这笔借书/收了这笔罚款"，业务字段已完全覆盖
2. 独立审计表需要 AOP 或事件机制，与本项目"教学可解释"目标冲突
3. 业务字段可被查询接口直接使用（如"查询该图书管理员经办的借阅"），审计表则需额外关联

**日志级别约定**：

| 级别 | 用途 |
|---|---|
| `ERROR` | 未处理异常、事务回滚 |
| `WARNING` | 业务规则拦截（如超额度拒绝借书） |
| `INFO` | 关键写操作成功（借书、还书、办证） |
| `DEBUG` | SQL 与详细流程（仅开发环境） |

**严禁记录**：明文密码、完整 JWT token、密码哈希。

### 6.5 时间处理

**统一约定**（宪法第十四条、决策 D-01b）：

| 环节 | 处理方式 |
|---|---|
| 数据库存储 | UTC 时间戳 |
| 领域层计算 | 全部以 UTC 进行 |
| API 传输 | ISO 8601 带时区，如 `2026-09-19T06:44:25Z` |
| 前端显示 | 转换为北京时间（UTC+8） |

**实现要点**：

- 统一使用 `datetime.now(timezone.utc)`，**禁用** `datetime.now()`（返回本地时间）
- 超期判定**精确到时刻**（决策 D-13 冲突裁定）：`returned_at > due_at` 即为超期，不按自然日
- `due_at` 在借出时**快照**，后续规则修改不追溯（BR-050）

### 6.6 CORS 与配置

| 项 | 设计 |
|---|---|
| CORS | 允许前端开发服务器源；生产环境收紧 |
| 配置来源 | 环境变量 + `.env`（`pydantic-settings`） |
| 敏感配置 | `SECRET_KEY`、数据库 URL 从环境变量读取，**不入库不提交** |
| 配置读取位置 | **仅基础设施层与启动入口**，领域层不得读环境变量（宪法第五条违反示例） |

---

## 7. 部署视图

```
┌─────────────────────────────────────────────────────┐
│                    客户端                             │
│  浏览器（实验二：TypeScript 前端）                     │
│  或 API 调试工具（实验一验收：Swagger UI / curl）       │
└─────────────────────────────────────────────────────┘
                        │  HTTP
                        ↓
┌─────────────────────────────────────────────────────┐
│              应用进程（单进程）                        │
│  ┌───────────────────────────────────────────────┐  │
│  │  FastAPI 应用（uvicorn 承载）                  │  │
│  │  ├─ Routers（表现层）                          │  │
│  │  ├─ Services（应用层）                         │  │
│  │  ├─ Domain（领域层）                           │  │
│  │  └─ Infrastructure（基础设施层）                │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────┐
│              数据存储                                 │
│  SQLite 单文件（backend/data/library.db）             │
│  测试时使用内存库（:memory:）                          │
└─────────────────────────────────────────────────────┘
```

**部署形态**：单体单进程。**不引入**容器编排、负载均衡、反向代理——见 §1.3。

**启动流程**：

1. 读取环境变量配置
2. 建表（SQLAlchemy `create_all`）
3. 执行初始化脚本：写入初始借阅规则、初始罚款规则、**首个系统管理员账号**

```bash
python scripts/init_db.py --admin-username admin --admin-password '<密码>'
```

4. 启动 uvicorn

**初始化脚本的必要性**：决策 D-04 规定系统管理员**只能通过初始化脚本创建，不提供在线创建接口**。故该脚本是系统可用的前置条件。

**初始化密码的处理**（详见 `13-database-design.md` §7.1）：密码通过**命令行参数**传入，脚本内**不设默认值**。缺失则报错退出。理由：默认密码会随 Git 提交进入仓库历史，事后删除代码也无法消除历史中的凭据。

---

## 8. 目录结构

```
expr_proj/
├── specs/                          # 规格文档（实验一交付物）
├── docs_expr_description/          # 实验文档（只读，gitignore）
├── worklog.md                      # Agent 行为时序记录
├── frontend/                       # 前端（实验二）
└── backend/                        # 后端
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                 # 应用入口、异常处理器注册、CORS
    │   │
    │   ├── presentation/           # 表现层
    │   │   ├── routers/
    │   │   │   ├── auth_router.py
    │   │   │   ├── card_router.py
    │   │   │   ├── catalog_router.py
    │   │   │   ├── circulation_router.py
    │   │   │   ├── reservation_router.py
    │   │   │   ├── query_router.py
    │   │   │   └── policy_router.py
    │   │   ├── schemas/            # Pydantic DTO
    │   │   │   ├── auth_schemas.py
    │   │   │   ├── circulation_schemas.py
    │   │   │   └── ...
    │   │   └── dependencies.py     # 鉴权守卫、服务注入
    │   │
    │   ├── application/            # 应用服务层
    │   │   ├── services/
    │   │   │   ├── auth_service.py
    │   │   │   ├── card_service.py
    │   │   │   ├── catalog_service.py
    │   │   │   ├── circulation_service.py
    │   │   │   ├── reservation_service.py
    │   │   │   ├── query_service.py
    │   │   │   └── policy_service.py
    │   │   ├── ports/              # Repository 接口定义
    │   │   │   ├── reader_repository.py
    │   │   │   ├── card_repository.py
    │   │   │   ├── catalog_repository.py
    │   │   │   ├── loan_repository.py
    │   │   │   ├── reservation_repository.py
    │   │   │   ├── fine_repository.py
    │   │   │   └── policy_repository.py
    │   │   ├── unit_of_work.py     # 事务边界抽象
    │   │   └── exceptions.py       # 应用层异常
    │   │
    │   ├── domain/                 # 领域层（零框架依赖）
    │   │   ├── entities/
    │   │   │   ├── reader.py
    │   │   │   ├── borrow_card.py
    │   │   │   ├── book_title.py
    │   │   │   ├── library_item.py
    │   │   │   ├── loan.py
    │   │   │   ├── reservation.py
    │   │   │   └── fine_record.py
    │   │   ├── value_objects/
    │   │   │   ├── card_number.py
    │   │   │   ├── barcode.py
    │   │   │   ├── isbn.py
    │   │   │   ├── money.py
    │   │   │   └── date_range.py
    │   │   ├── enums/
    │   │   │   └── *.py
    │   │   ├── domain_services/
    │   │   │   ├── borrow_eligibility_service.py
    │   │   │   ├── renewal_service.py
    │   │   │   └── reservation_queue_service.py
    │   │   ├── policies/
    │   │   │   ├── borrow_policy.py
    │   │   │   └── fine_rule.py
    │   │   ├── factories/
    │   │   │   ├── reader_factory.py
    │   │   │   └── library_item_factory.py
    │   │   └── exceptions.py       # 领域异常
    │   │
    │   └── infrastructure/         # 基础设施层
    │       ├── db/
    │       │   ├── session.py
    │       │   └── base.py
    │       ├── models/             # SQLAlchemy ORM 映射
    │       │   ├── reader_model.py
    │       │   ├── card_model.py
    │       │   ├── catalog_model.py
    │       │   ├── loan_model.py
    │       │   ├── reservation_model.py
    │       │   ├── fine_model.py
    │       │   └── policy_model.py
    │       ├── repositories/       # Repository 接口实现
    │       │   └── sqlalchemy_*.py
    │       ├── mappers/            # ORM ↔ 领域对象转换
    │       │   └── *.py
    │       └── security/
    │           ├── jwt.py
    │           └── password.py
    │
    ├── scripts/
    │   └── init_db.py              # 初始化规则 + 首个系统管理员
    ├── tests/
    │   ├── unit/                   # 领域层单测（不依赖 DB）
    │   └── integration/            # API 端到端测试
    ├── requirements.txt
    └── README.md
```

**目录与分层对应关系**：

| 目录 | 层 | 可被谁依赖 |
|---|---|---|
| `presentation/` | 表现层 | 无人依赖它 |
| `application/` | 应用层 | `presentation/` |
| `domain/` | 领域层 | `application/`、`infrastructure/` |
| `infrastructure/` | 基础设施层 | 无（实现接口，被注入） |

**`mappers/` 的必要性**：ORM 模型与领域实体是**两套对象**。`BookTitle` 领域实体有 `available_items()` 等行为方法，ORM 模型不应有。Mapper 负责双向转换，避免 ORM 模型泄漏到领域层（宪法 C-4 的延伸）。

**这个结构比 `05-domain-model.md` 的 7 个限界上下文模块更扁平**——前者是**业务视角**（模块划分），后者是**技术视角**（分层划分）。包图（`08-package-diagram.md`）将显式呈现两套视角的映射。

---

## 9. 关键流程的分层落点

### 9.1 办理借书（UC-101）

| 步骤 | 层 | 组件 |
|---|---|---|
| 接收请求、校验参数格式 | 表现层 | `circulation_router.borrow_book()`、`BorrowBookRequest` |
| 校验角色为图书管理员 | 表现层 | `require_role(Role.LIBRARIAN)` |
| 开启事务 | 应用层 | `CirculationService.borrow_book()` |
| 加载借阅证、读者、借阅、预约、罚款、副本、规则 | 应用层 + 基础设施 | Repository |
| **资格判定（6 步固定顺序）** | **领域层** | `BorrowEligibilityService.check_eligibility()` |
| 创建 `Loan`、快照 `due_at` | 领域层 | `Loan.create()` |
| 副本置 `BORROWED` | 领域层 | `LibraryItem.mark_borrowed()` |
| 落库、提交事务 | 应用层 + 基础设施 | Repository + UoW |
| 组装响应 | 表现层 | `BorrowBookResponse` |

**失败路径**：任一步抛 `BusinessRuleError` → 事务回滚 → 全局异常处理器映射为 409/400。

### 9.2 办理还书（UC-102）

| 步骤 | 层 | 组件 |
|---|---|---|
| 接收请求（仅凭馆藏条码） | 表现层 | `circulation_router.return_book()` |
| 查找未归还 `Loan` | 应用层 | `LoanRepository.find_by_item()` |
| 计算超期天数与罚款 | **领域层** | `Loan.overdue_days()`、`FineRule.calculate_fine()` |
| 生成 `FineRecord`（若有罚款） | 领域层 | `FineRecord.create()` |
| 更新 `Loan.returned_at` | 领域层 | `Loan.return_item()` |
| **处理预约预留** | **领域层** | `ReservationQueueService.peek()` → `Reservation.mark_ready()` → `LibraryItem.mark_returned(has_reservation=True)` |
| 落库、提交事务 | 应用层 + 基础设施 | Repository + UoW |

**注意**：还书是**跨模块协调最多的操作**（流通 + 罚款 + 预约 + 书目），但所有业务判定都在领域层，应用层只做编排与事务。

### 9.3 预约图书（UC-005）

| 步骤 | 层 | 组件 |
|---|---|---|
| 接收请求 | 表现层 | `reservation_router.create_reservation()` |
| 校验读者身份与资源归属 | 应用层 | 从 token 取 `reader_id` |
| 加载题录与现有预约队列 | 应用层 | Repository |
| **校验：所有副本均不可借、无重复预约、队列未满** | **领域层** | `ReservationQueueService.can_reserve()` |
| 创建 `Reservation`（`ACTIVE`） | 领域层 | `Reservation.create()` |
| 落库、提交事务（含队列并发安全） | 应用层 + 基础设施 | UoW |

### 9.4 规则维护（UC-213 / UC-214）

| 步骤 | 层 | 组件 |
|---|---|---|
| 接收请求 | 表现层 | `policy_router.update_borrow_policy()` |
| 校验角色为系统管理员 | 表现层 | `require_role(Role.ADMIN)` |
| 校验数值合法性（正整数 / 非负数） | 领域层 | `BorrowPolicy.update()` |
| 记录 `updated_at` / `updated_by` | 领域层 | 实体方法内 |
| 落库、提交事务 | 应用层 + 基础设施 | `PolicyRepository` |

**关键**：修改**不追溯**已有借阅记录（BR-050），因为 `due_at` 与 `unit_price` 已在操作时快照。领域层无须特殊处理——这是快照设计的自然结果。

---

## 10. 架构决策记录（ADR）

> 记录有争议或非显然的架构取舍，说明**考虑过的替代方案**与**拒绝理由**。供人工审查质询。

### ADR-01：采用四层分层而非三层

- **决策**：表现层 / 应用层 / 领域层 / 基础设施层
- **替代方案**：三层（表现 / 业务 / 数据）
- **选择理由**：三层的"业务层"会同时容纳用例编排与领域规则，导致 `CirculationService` 里既开事务又写"5 册上限"。实验明确要求区分 Service Layer 与领域规则，且宪法第五条已固化四层。
- **代价**：文件数量增加，需维护 Mapper 转换。

### ADR-02：Repository 接口定义在应用层而非领域层

- **决策**：接口放 `application/ports/`，实现放 `infrastructure/repositories/`
- **替代方案**：接口放领域层（经典 DDD 做法）
- **选择理由**：本项目的领域实体是**充血但不具备持久化透明性**的——实体不需要"自我保存"能力。接口放应用层更贴近实际使用者（应用服务），且减少领域层的抽象负担。
- **代价**：严格 DDD 视角下这是折衷；但依赖倒置的效果等价。

### ADR-03：不引入乐观锁版本号

- **决策**：并发控制依赖 SQLite 写串行化 + 事务原子性
- **替代方案**：实体加 `version` 字段 + 提交时校验
- **选择理由**：① 本项目定位为课程实验，无并发压力；② 引入版本号会让每个实体、每个更新路径都要处理冲突重试，复杂度显著上升；③ SQLite 的写操作本身串行，事务已能保证"不会部分成功"。
- **风险与缓解**：若后续更换为 PostgreSQL 且存在真实并发，需补充乐观锁。已在包图与数据库设计文档中留有 `version` 字段的扩展位。

### ADR-04：不做独立审计日志表

- **决策**：操作人以业务字段形式留存（`librarian_id` / `issued_by` / `operator_id` / `updated_by`）
- **替代方案**：统一 `audit_logs` 表 + AOP 拦截自动记录
- **选择理由**：① 实验要求的审计粒度是具体业务操作，业务字段已覆盖；② AOP 与事件机制与本项目"教学可解释"目标冲突；③ 业务字段可直接用于查询接口，审计表需额外 join。
- **代价**：无法自动记录"某人查看了某数据"这类读操作。本项目无此要求。

### ADR-05：ORM 模型与领域实体分离，用 Mapper 转换

- **决策**：`infrastructure/models/` 与 `domain/entities/` 是两套类，`mappers/` 负责转换
- **替代方案**：领域实体直接标注 SQLAlchemy 映射（Active Record）
- **选择理由**：宪法第五条明确禁示领域层 import sqlalchemy。Active Record 会让领域实体带上 `__tablename__`、`relationship()` 等持久化关注点，并使领域层无法脱离数据库单测。
- **代价**：需编写并维护 ~11 组 Mapper。这是本项目为满足宪法约束付出的**必要代价**。

### ADR-06：采用 SQLite 而非 PostgreSQL

- **决策**：SQLite 单文件
- **替代方案**：PostgreSQL（Docker 部署）
- **选择理由**：零部署成本、单文件便于提交与演示、pytest 可用 `:memory:` 获得高速测试。
- **代价**：无行级锁、无完整并发能力。通过 Repository 接口隔离，迁移只需替换实现层。

### ADR-07：弃用独立的审计 Use Case，改为业务字段内嵌

见 ADR-04，此处不重复。

### ADR-08：学生/教师账号与员工账号不共享基类

- **决策**：`Reader` 与 `Librarian` / `SystemAdmin` 无继承关系，也不抽 `Account` 基类
- **替代方案**：抽 `Account` 基类承载 `username` / `password_hash` / `login()`
- **选择理由**：① 仅"能登录"不足以构成领域继承（详见 `06-domain-class-diagram.md` §10.2）；② 登录是应用层关注点（`AuthService` 按角色查不同表）；③ 抽基类会产生贫血父类，反而增加理解成本。
- **代价**：`AuthService` 需按角色分派到不同 Repository。这个复杂度是小而局部的。

---

## 11. 架构与需求的追溯

| 需求/规则 | 架构支撑 |
|---|---|
| FR-015 ~ FR-020 借阅流通 | `CirculationService` + `BorrowEligibilityService` + 事务边界 |
| FR-021 ~ FR-024 预约 | `ReservationService` + `ReservationQueueService` |
| FR-025 ~ FR-026 罚款 | `FineRecord` 实体 + `FineRule` 策略 + `Money` 值对象 |
| FR-027 ~ FR-028 规则维护 | `PolicyService` + 规则存库（C-6） |
| BR-049 规则不得硬编码 | Strategy 查表实现（§4.1） |
| BR-045 密码哈希 | 基础设施层 `security/password.py` |
| BR-036 ~ BR-042 软删除 | 实体 `is_deleted` / `ItemStatus.REMOVED` + 应用层过滤 |
| BR-050 规则修改不追溯 | `Loan.due_at` 快照 + `FineRecord.unit_price` 快照 |
| NFR-001 ~ NFR-014 非功能 | 分层架构、统一异常、事务边界、UTC 时间处理 |
| 宪法第五条 分层 | §2 四层划分 + §2.4 可执行检查 |
| 宪法第六条 MVC | §3 映射关系 + 禁止示例 |
| 宪法第七条 权限 | §6.1 鉴权守卫 + 权限矩阵 |
| 宪法第八条 规则集中 | §4 模式使用位置 |
| 宪法第九条 事务 | §6.3 事务边界表 |
| 宪法第十四条 时间 | §6.5 时间处理 |

---

## 12. 人工审查重点自查

| 审查项 | 自查结果 |
|---|---|
| 分层是否清晰、依赖是否单向？ | ✅ §2.1 给出四层图与依赖方向；§2.3 说明依赖倒置；§2.4 给出可执行检查项 |
| 领域层是否依赖框架？ | ✅ 明确禁止，并提供"删除 fastapi/sqlalchemy 后仍可单测"的机械检验标准 |
| 业务规则是否在领域层？ | ✅ §2.2.3 领域层职责；§4.1 给出 Strategy 正确/错误代码对照 |
| Router 是否只做转发？ | ✅ §3.3 给出宪法原文的违规示例与正确写法，并定义"典型 1-3 行"的体量标准 |
| 事务边界是否明确？ | ✅ §6.3 列出 5 个操作的事务范围与提交点 |
| 设计模式使用位置是否有据？ | ✅ §4 表格给出模式 / 位置 / 解决的问题 / 对应代码；§4.2 界定 Factory 边界 |
| 权限控制是否服务端完成？ | ✅ §6.1 鉴权守卫 + 资源归属校验；给出 `/readers/{id}/loans` 反例 |
| 时间处理是否统一？ | ✅ §6.5；明确禁用 `datetime.now()` |
| 目录结构是否反映分层？ | ✅ §8 目录树 + 层对应表 |
| 关键流程落点是否明确？ | ✅ §9 拆解 4 个流程的分层落点 |
| 是否有过度设计？ | ✅ §1.3 明确不做清单；ADR-03/04 拒绝乐观锁与审计表 |
| 架构决策是否有记录？ | ✅ §10 记录 8 条 ADR，含替代方案与拒绝理由 |

---

## 13. 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|---|---|---|---|
| v1.0 | 2026-09-19 | 初版制定。四层架构、MVC 映射、模式位置、技术选型、6 类横切关注点、部署视图、目录结构、4 个关键流程落点、8 条 ADR。 | Agent 起草 |
