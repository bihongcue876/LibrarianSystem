# 编码任务拆解（Implementation Tasks）

> **文档编号**：`specs/16-tasks.md`
> **制定依据**：全部 specs（`constitution.md`、`02`、`03`、`05`、`07`、`08`、`09`、`13`、`14`、`15`）
> **版本**：v1.0
> **日期**：2026-09-20
>
> **本文件是编码 Agent 的执行清单**。每个任务粒度控制在「一次 Agent 会话可完成」，且都有可机械判定的验收标准。
>
> **代码根目录**：`backend/`（目录结构见 `07-architecture.md` §8）

---

## 0. 执行约定（对所有任务生效）

### 0.1 禁止修改的文件

**实现阶段不得修改任何 specs 文件**（`specs/` 目录整体只读）。规格若有问题，按以下流程处理：

1. 停止编码，记录问题（文件、章节、期望行为 vs 实际行为）；
2. 向人工提出规格修订请求，由人工决定是否修订并重新冻结 baseline；
3. **不得**为了让代码跑通而私自改规格，也**不得**在代码中绕过规格约束。

### 0.2 分层红线（每个任务都必须自检）

| 编号 | 红线 | 自检命令 |
|---|---|---|
| R-1 | `presentation/` 不得依赖 `infrastructure/` | `grep -rn "infrastructure" backend/app/presentation/` → 0 命中 |
| R-2 | `application/` 不得依赖 `infrastructure/` 具体类 | `grep -rn "from app.infrastructure" backend/app/application/` → 0 命中 |
| R-3 | `domain/` 不得依赖任何框架或其他层 | `grep -rn "fastapi\|sqlalchemy\|app.application\|app.infrastructure" backend/app/domain/` → 0 命中 |
| D-7 | `entities/` 不得依赖 `domain_services/` 与 `factories/` | `grep -rn "domain_services\|factories" backend/app/domain/entities/` → 0 命中 |
| BR-049 | `policies/` 不得硬编码规则数值 | `grep -rn "== 5\|== 10\|== 15\|== 20\|0\.2\|0\.5\|1\.0" backend/app/domain/policies/` → 0 命中 |

### 0.3 任务依赖图

```
TASK-001 初始化项目结构
    ↓
TASK-002 领域枚举与值对象 ──→ TASK-003 领域实体 ──→ TASK-006 领域服务
    ↓                              ↓                     ↓
TASK-004 ORM 模型与 Mapper ←───────┘                     │
    ↓                                                    │
TASK-005 Repository 接口与实现                           │
    ↓                                                    │
TASK-007 借阅规则策略 ──┐                                 │
TASK-008 罚款规则策略 ──┴─→ TASK-009 账号与认证          │
                              ↓                          │
                        TASK-010 借阅证管理               │
                        TASK-011 书目与馆藏管理           │
                              ↓                          ↓
                        TASK-012 借书 ←───────────────────┘
                              ↓
                        TASK-013 还书与罚款收缴
                              ↓
                        TASK-014 续借
                        TASK-015 预约
                        TASK-016 查询与统计
                        TASK-017 权限与规则维护
                              ↓
                        TASK-018 完善测试与分层校验
```

---

## TASK-001 初始化项目结构

| 项 | 内容 |
|---|---|
| **任务目标** | 建立 `07-architecture.md` §8 规定的四层目录骨架与可启动的 FastAPI 应用，**不含任何业务逻辑** |
| **输入规格** | `07-architecture.md` §8（目录结构）、§5（技术选型） |
| **允许修改** | `backend/**`（全部新建） |
| **禁止修改** | `specs/**`、`frontend/**` |
| **实现要求** | 1. 创建 `app/{presentation,application,domain,infrastructure}` 四层目录及 `__init__.py`；2. 建立各层子包（routers/schemas、services/ports、entities/value\_objects/enums/domain\_services/policies/factories、db/models/repositories/mappers/security）；3. 实现 `main.py`：创建 FastAPI 实例、注册全局异常处理器占位、配置 CORS；4. 提供 `GET /api/health` 健康检查；5. 编写 `requirements.txt`（fastapi、uvicorn、sqlalchemy、pydantic、python-jose 或 pyjwt、bcrypt、pytest、httpx）；6. **不实现任何业务接口** |
| **验收标准** | ① `uvicorn app.main:app` 可启动；② `GET /api/health` 返回 200；③ 目录结构与 `07` §8 逐项对应；④ 无业务逻辑代码 |
| **建议测试** | `tests/integration/test_health.py`：断言健康检查返回 200 |

---

## TASK-002 实现领域枚举与值对象

| 项 | 内容 |
|---|---|
| **任务目标** | 实现 `05-domain-model.md` 定义的 7 个枚举与 5 个值对象 |
| **输入规格** | `05-domain-model.md` §3.2、§3.3、§4.4~§4.7、§5.2、§5.3、§6.2、§7.2、§7.3 |
| **允许修改** | `backend/app/domain/enums/**`、`backend/app/domain/value_objects/**`、`backend/tests/unit/**` |
| **禁止修改** | `backend/app/domain/entities/**`、`specs/**` |
| **实现要求** | 1. 枚举：`ReaderType`、`ItemType`、`ItemStatus`、`CardStatus`、`LoanStatus`、`ReservationStatus`、`FineStatus`，取值须与 `05` 完全一致；2. 值对象：`CardNumber`（正则 `^CARD\d{4}\d{6}$` + `generate` + `is_valid`）、`Barcode`（`BC` + 8 位序号）、`Isbn`（`is_valid` + `normalize`）、`Money`（内部 **`Decimal`，`quantize(0.01)`，禁止 `float`**，提供 `multiply`/`min_with_cap`/`add`/`subtract`/`is_zero`）、`DateRange`（**不可变**，`extend_days` 返回新对象）；3. 值对象使用 `@dataclass(frozen=True)` 实现不可变 |
| **验收标准** | ① 枚举取值与 `05` 逐项一致；② `Money` 内部为 `Decimal`，`0.20 × 3 == 0.60` 严格成立；③ `DateRange.extend_days` 不修改原对象；④ 领域层无框架导入（R-3） |
| **建议测试** | `tests/unit/test_value_objects.py`：证号/条码格式校验、ISBN 校验、`Money` 精度与封顶、`DateRange` 不可变性 |

---

## TASK-003 实现领域实体

| 项 | 内容 |
|---|---|
| **任务目标** | 实现 14 个领域实体（含抽象基类与子类）及全部行为方法 |
| **输入规格** | `05-domain-model.md` §2~§8、`06-domain-class-diagram.md` |
| **允许修改** | `backend/app/domain/entities/**`、`backend/app/domain/factories/**`、`backend/tests/unit/**` |
| **禁止修改** | `backend/app/domain/domain_services/**`、`specs/**` |
| **实现要求** | 1. **不得使用 SQLAlchemy 注释或 `Column()`**——领域实体是纯 Python 类（R-3、ADR-05）；2. `Reader`（抽象）与 `StudentReader`/`TeacherReader` 覆写 `borrow_limit(policy)`/`borrow_days(policy)`，**数值全部委托给 `BorrowPolicy` 查询**，不得硬编码；3. `LibraryItem`（抽象）与 `Book`/`Magazine`/`Thesis`，状态机方法 `mark_borrowed`/`mark_returned(has_reservation)`/`mark_reserved`/`mark_lost`/`mark_damaged`/`remove` 须拒绝非法流转；4. `BorrowCard` 状态机 `issue`/`cancel`/`restore`/`suspend`/`resume` 守卫状态，**禁止外部直接改 `status`**；5. `Loan`：`create`（快照 `due_at`）、`is_overdue`、`overdue_days`、`can_renew`、`renew`、`return_item`；6. `Reservation`：`create`/`mark_ready`/`cancel`/`expire`/`is_expired`；7. `FineRecord`：`create`（**快照 `unit_price`**）/`pay`/`is_unpaid`，含 `operator_role` 字段；8. `BorrowPolicy`/`FineRule` 为策略对象（见 TASK-007/008，此处仅定义接口引用）；9. `ReaderFactory`/`LibraryItemFactory` 按类型枚举分派创建子类 |
| **验收标准** | ① 14 个实体齐备；② `grep -rn "sqlalchemy" backend/app/domain/entities/` → 0 命中；③ 非法状态流转抛领域异常；④ `Loan.create` 后修改 `BorrowPolicy` 不影响已有 `due_at`；⑤ 实体不调用领域服务（D-7） |
| **建议测试** | `tests/unit/test_entities.py`：借阅证状态机、副本状态机、`Loan` 超期计算与续借边界、`Reservation` 失效判定 |

---

## TASK-004 实现 ORM 模型与 Mapper

| 项 | 内容 |
|---|---|
| **任务目标** | 实现 11 张表的 SQLAlchemy 映射与领域对象双向转换 |
| **输入规格** | `13-database-design.md` 全文（表结构、字段、约束、索引、单表继承策略） |
| **允许修改** | `backend/app/infrastructure/db/**`、`backend/app/infrastructure/models/**`、`backend/app/infrastructure/mappers/**`、`backend/tests/integration/conftest.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 7 组 ORM 模型映射 11 张表（9 实体表 + 2 规则表）；2. **单表继承**：`readers` 表用 `reader_type` 判别列承载 3 个读者类；`library_items` 表用 `item_type` 判别列承载 4 个副本类（决策 D-50）；3. `MoneyType` 自定义类型：**底层存 TEXT**（SQLite 无 DECIMAL，`Numeric` 会降级为 REAL 导致精度丢失），读写时与 `Decimal` 互转；4. 索引按 `13` §4 实现，含 **3 个部分唯一索引**（如 ISBN 仅对活跃记录唯一）；5. CHECK 约束按 `13` 实现（枚举取值域、`loans.status` 只允许 `BORROWED`/`RETURNED`、`operator_role` 取值域等）；6. **不建触发器**（业务逻辑留在领域层）；7. 7 个 Mapper 实现 `to_domain` / `to_model` 双向转换 |
| **验收标准** | ① `Base.metadata.create_all()` 建表成功；② 表数 = 11，索引数 = 20；③ 金额读写后 `Decimal` 精度不变；④ 软删除标记字段齐备；⑤ Mapper 往返转换不丢字段 |
| **建议测试** | `tests/integration/test_models.py`：建表、约束生效（插入非法枚举值应失败）、金额精度往返、软删除字段默认值 |

---

## TASK-005 实现 Repository 接口与实现

| 项 | 内容 |
|---|---|
| **任务目标** | 定义 7 个 Repository Protocol（应用层）并给出 SQLAlchemy 实现（基础设施层） |
| **输入规格** | `08-package-diagram.md` §4、§6；`09-design-model.md` §2~§9 的 Repository 列 |
| **允许修改** | `backend/app/application/ports/**`、`backend/app/infrastructure/repositories/**` |
| **禁止修改** | `backend/app/domain/**`、`backend/app/application/services/**`、`specs/**` |
| **实现要求** | 1. 接口用 `typing.Protocol` 定义在 `application/ports/`，**返回领域实体而非 ORM 模型**；2. 实现类 `SqlAlchemy*Repository` 位于 `infrastructure/repositories/`，内部使用对应 Mapper；3. **Repository 只负责持久化**：不做业务判定、不提交事务；4. 必须提供的方法（至少）：`ReaderRepository.find_by_id` / `find_by_username` / `add` / `update`；`CardRepository.find_by_card_no` / `find_active_by_reader` / `next_sequence` / `add` / `update`；`CatalogRepository.find_by_barcode` / `find_title_by_id` / `find_titles` / `add_title` / `add_item` / `update_item` / `next_barcode_sequence` / `collection_stats`；`LoanRepository.find_active_by_item` / `find_active_by_reader` / `find_by_reader` / `add` / `update`；`ReservationRepository.find_active_by_title` / `find_active_by_reader` / `add` / `update`；`FineRepository.find_unpaid_by_reader` / `find_by_id` / `add` / `update`；`PolicyRepository.get_borrow_policy` / `get_fine_rule` / `list_borrow_policies` / `list_fine_rules` / `update_borrow_policy` / `update_fine_rule`；5. **软删除过滤**：查询默认排除 `is_deleted = 1` 的记录（BR-037） |
| **验收标准** | ① 7 个 Protocol + 7 个实现类齐备；② 接口签名无 SQLAlchemy 类型泄漏（不出现 `Session`、`Model`）；③ `grep -rn "from app.infrastructure" backend/app/application/` → 0 命中（R-2） |
| **建议测试** | `tests/integration/test_repositories.py`：CRUD 往返、软删除过滤、`next_sequence` 并发递增 |

---

## TASK-006 实现领域服务

| 项 | 内容 |
|---|---|
| **任务目标** | 实现 3 个领域服务：借阅资格判定、续借、预约队列 |
| **输入规格** | `05-domain-model.md` §5.4、§5.5、§6.3；`03-use-cases.md` UC-101 |
| **允许修改** | `backend/app/domain/domain_services/**`、`backend/app/domain/exceptions.py`、`backend/tests/unit/**` |
| **禁止修改** | `backend/app/domain/entities/**`、`specs/**` |
| **实现要求** | 1. `BorrowEligibilityService` **纯函数式**——只判定、不改状态、不访问数据库；`check_eligibility` 按**固定顺序**「借阅证 → 数量 → 超期 → 罚款 → 副本」执行，**遇首个失败即返回**，不累积错误；2. `check_quota` 的额度口径 = **未归还借阅 + 有效预约**（BR-007）；3. `RenewalService.can_renew` 判定「未超期」且「`renew_count` < 2」且「未超额」；**存在预约不影响续借**（BR-018）；4. `ReservationQueueService`：`enqueue`（上限 5 人）、`peek`、`position_of`、`dequeue_expired`、`can_reserve`（含重复校验与可借性校验）；5. 队列排序**按 `created_at` 升序**，不得用自增主键；6. 领域异常定义在 `domain/exceptions.py`（`NotFoundError`、`ValidationError`、`BusinessRuleError`、`ConflictError`），携带 `code`、`message`、`http_status` |
| **验收标准** | ① 校验顺序可被单测断言（构造多个失败条件时返回**第一个**错误）；② 领域服务不修改传入实体状态；③ `grep -rn "domain_services\|factories" backend/app/domain/entities/` → 0 命中（D-7） |
| **建议测试** | `tests/unit/test_domain_services.py`：六项校验顺序、额度口径含预约、续借边界、队列排序与上限 |

---

## TASK-007 实现借阅规则策略

| 项 | 内容 |
|---|---|
| **任务目标** | 实现 `BorrowPolicy` 策略对象，支持 5 种读者类型的额度与期限 |
| **输入规格** | `09-design-model.md` §12；`05-domain-model.md` §8.1；`02-requirements.md` BR-006 |
| **允许修改** | `backend/app/domain/policies/borrow_policy.py`、`backend/tests/unit/test_borrow_policy.py`、`backend/scripts/init_db.py`（种子数据部分） |
| **禁止修改** | `specs/**` |
| **实现要求** | 1. 提供 `limit_for(reader_type) -> int`、`days_for(reader_type) -> int`、`update(max_count, days, operator)`；2. **规则数值不得硬编码在代码中**——`BorrowPolicy` 从注入的数据（Repository 读出）构造，查表返回；3. 支持：`COLLEGE` 5 册/30 天、`UNDERGRADUATE` 5 册/30 天、`GRADUATE` 10 册/60 天、`DOCTOR` 15 册/90 天、`TEACHER` 20 册/90 天；4. 种子数据写入 `scripts/init_db.py`（这些是**数据**，不是代码分支，允许出现在脚本中）；5. `update` 记录 `updated_at` 与 `updated_by` |
| **验收标准** | ① 5 种类型查询值正确；② `grep -rn "== 5\|== 10\|== 15\|== 20" backend/app/domain/policies/` → 0 命中；③ 在线修改后新借阅按新规则计算，已有 `Loan.due_at` 不变（BR-050） |
| **建议测试** | `tests/unit/test_borrow_policy.py`：5 种类型查表、未知类型报错、`update` 后查询值变化 |

---

## TASK-008 实现罚款规则策略

| 项 | 内容 |
|---|---|
| **任务目标** | 实现 `FineRule` 策略对象，支持 5 种借出物类型的罚款计算 |
| **输入规格** | `09-design-model.md` §8.2、§12；`05-domain-model.md` §8.2；`02-requirements.md` BR-027~BR-030 |
| **允许修改** | `backend/app/domain/policies/fine_rule.py`、`backend/tests/unit/test_fine_rule.py`、`backend/scripts/init_db.py`（种子数据部分） |
| **禁止修改** | `specs/**` |
| **实现要求** | 1. 提供 `calculate_fine(item_type, overdue_days) -> Money`、`billed_days(overdue_days) -> int`、`update(daily_price, grace_days, max_amount, operator)`；2. 计算公式：`计罚天数 = max(超期天数 − 宽限天数, 0)`；`金额 = min(计罚天数 × 日单价, 封顶金额)`；3. 支持：`CHINESE_BOOK` 0.20、`FOREIGN_BOOK` 0.50、`CHINESE_MAGAZINE` 0.10、`FOREIGN_MAGAZINE` 0.20、`THESIS` 1.00（元/天），宽限 2 天，封顶 100.00 元；4. `overdue_days ≤ 0` 时返回 0 元；5. **全程使用 `Money`（`Decimal`），禁止 `float`** |
| **验收标准** | ① 5 种类型金额正确；② 宽限期 2 天内罚款为 0；③ 封顶 100 元生效；④ `0.20 × 3 == 0.60` 严格成立；⑤ 规则数值不出现在 `policies/` 的代码分支中 |
| **建议测试** | `tests/unit/test_fine_rule.py`：TC-020、TC-021 + 5 种类型参数化测试 |

---

## TASK-009 实现账号与认证

| 项 | 内容 |
|---|---|
| **任务目标** | 实现注册、登录、员工账号增删、密码重置 |
| **输入规格** | `14-api-spec.md` §2；`03-use-cases.md` UC-001/002/206/207；`02-requirements.md` FR-001~FR-004、BR-045~BR-048 |
| **允许修改** | `backend/app/presentation/routers/auth_router.py`、`backend/app/presentation/schemas/auth_schemas.py`、`backend/app/presentation/dependencies.py`、`backend/app/application/services/auth_service.py`、`backend/app/application/exceptions.py`、`backend/app/infrastructure/security/**`、`backend/tests/integration/test_auth.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 密码用 **bcrypt** 哈希（BR-045），严禁明文或 MD5；2. JWT 有效期 **24 小时**，不提供 refresh token（BR-046）；3. 登录失败提示**统一**为"用户名或密码错误"，不区分用户名不存在与密码错误（BR-047）；4. 用户名全局唯一且**软删除不释放**（Q-03 裁定）；5. `dependencies.py` 提供 `get_current_account`（解析 JWT）与 `require_role(*roles)`（角色守卫），**权限校验必须在服务端**（BR-042）；6. 注册成功但**无借阅资格**（BR-012）；7. 系统管理员账号只能由初始化脚本创建，不提供在线创建接口（FR-004） |
| **验收标准** | ① TC-001~TC-004 通过；② 数据库中无明文密码；③ 越权访问返回 403 `PERMISSION_DENIED`；④ Token 过期后返回 401 |
| **建议测试** | `tests/integration/test_auth.py`：TC-001、TC-002、TC-003、TC-004 |

---

## TASK-010 实现借阅证管理

| 项 | 内容 |
|---|---|
| **任务目标** | 实现借阅证的办理、注销、恢复、挂失、解挂、查询 |
| **输入规格** | `14-api-spec.md` §3；`03-use-cases.md` UC-201~UC-205；`09-design-model.md` §6 |
| **允许修改** | `backend/app/presentation/routers/card_router.py`、`presentation/schemas/card_schemas.py`、`backend/app/application/services/card_service.py`、`backend/tests/integration/test_card.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 仅 `SYSTEM_ADMIN` 可办理与管理借阅证（BR-041）；2. 读者必须存在且未软删除；3. **一证限制**：`ACTIVE`/`SUSPENDED` 计入，`CANCELLED` 不计入（BR-003）；4. 证号格式 `CARD` + 4 位年份 + 6 位序号，序号按年递增，全局唯一（BR-004）；5. 状态流转只能经实体方法，不得直接改字段；6. 注销时若该读者有未归还借阅则拒绝 |
| **验收标准** | ① TC-005、TC-006、TC-007 通过；② 证号格式与唯一性成立；③ 合法状态流转成功、非法流转返回 400 |
| **建议测试** | `tests/integration/test_card.py`：TC-005、TC-006、TC-007 + 状态机流转 |

---

## TASK-011 实现图书标题与馆藏管理

| 项 | 内容 |
|---|---|
| **任务目标** | 实现题录与馆藏副本的增删改与状态标记 |
| **输入规格** | `14-api-spec.md` §4；`03-use-cases.md` UC-208~UC-212；`09-design-model.md` §7 |
| **允许修改** | `backend/app/presentation/routers/catalog_router.py`、`presentation/schemas/catalog_schemas.py`、`backend/app/application/services/catalog_service.py`、`backend/tests/integration/test_catalog.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 仅 `SYSTEM_ADMIN` 可增删题录与副本（BR-041）；2. `BookTitle` 表示题名/作者/ISBN/出版社/类型；3. `LibraryItem` 表示物理副本，条码唯一（`BC` + 8 位序号）；4. 副本初始状态 `AVAILABLE`；5. 允许题录在**无副本**状态下存在（BR-014）；6. **ISBN 部分唯一索引**：仅对活跃记录查重，已软删除的相同 ISBN 可再次录入；7. 删除题录时其下副本**同步置 `REMOVED`**（FR-011 验收标准 3）；8. 删除题录时若存在未归还借阅，**删除不失败**——副本保持 `BORROWED` 直至归还，归还后置 `REMOVED`（FR-011 验收标准 4，**易实现错**）；9. `BORROWED` 状态的**副本**不可单独删除（BR-034）；10. 类型分派由 `LibraryItemFactory` 完成，不在服务里写 `if/elif` |
| **验收标准** | ① TC-033、TC-034 通过；② 条码唯一性成立；③ 非系统管理员调用返回 403；④ 删除题录后副本状态为 `REMOVED` |
| **建议测试** | `tests/integration/test_catalog.py`：TC-033、TC-034 + ISBN 部分唯一索引行为 |

---

## TASK-012 实现借书

| 项 | 内容 |
|---|---|
| **任务目标** | 实现借书前置校验与办理借书 |
| **输入规格** | `03-use-cases.md` UC-101 + FR-015；`10-sequence-borrow-book.md`；`09-design-model.md` §2；`15-test-plan.md` TC-008~TC-014 |
| **允许修改** | `backend/app/presentation/routers/circulation_router.py`、`presentation/schemas/circulation_schemas.py`、`backend/app/application/services/circulation_service.py`、`backend/app/application/unit_of_work.py`、`backend/tests/integration/test_borrow.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 仅 `LIBRARIAN`/`SYSTEM_ADMIN` 可办理（BR-040）；2. 输入借阅证号 + 馆藏条码；3. **六项校验按固定顺序**：借阅证 → 数量 → 超期 → 罚款 → 副本，**遇首个失败即返回**；4. 额度口径 = 未归还借阅 + 有效预约（BR-007）；5. 创建 `Loan` 并按读者类型设置 `due_at`（**快照**，BR-050）；6. 副本状态 → `BORROWED`；7. **事务边界在应用服务**：校验 + 创建 + 更新副本状态，全部成功才提交，任一失败回滚（**副本状态不得残留变更**）；8. `/precheck` 为只读预检查，**不产生副作用**（FR-015） |
| **验收标准** | ① TC-008~TC-014 全部通过；② 失败时无 `Loan` 记录且副本状态不变；③ `due_at` 按读者类型正确计算；④ 六项校验顺序可被测试断言 |
| **建议测试** | `tests/integration/test_borrow.py`：TC-008、TC-009、TC-010、TC-011、TC-012、TC-013、TC-014 |

---

## TASK-013 实现还书与罚款收缴

| 项 | 内容 |
|---|---|
| **任务目标** | 实现办理还书、超期罚款生成与收缴、预约预留处理 |
| **输入规格** | `03-use-cases.md` UC-102 + UC-102a + UC-104；`11-sequence-return-book.md`；`09-design-model.md` §3、§8；`15-test-plan.md` TC-015~TC-021、TC-036 |
| **允许修改** | `backend/app/presentation/routers/circulation_router.py`、`presentation/schemas/circulation_schemas.py`、`backend/app/application/services/circulation_service.py`、`backend/tests/integration/test_return.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 仅 `LIBRARIAN`/`SYSTEM_ADMIN` 可办理（BR-040）；2. **仅凭馆藏条码，不要求借阅证**；3. 条码不存在 → 404 `ITEM_NOT_FOUND`；无在借记录 → 404 `LOAN_NOT_FOUND`；4. 更新 `Loan.status` → `RETURNED` 并写 `returned_at`；5. 超期则生成 `FineRecord`（初始 `UNPAID`），**未超期不生成**（BR-029）；6. 副本去向：该题录有有效预约 → 队首置 `READY` + 副本置 `RESERVED`；无预约 → 副本置 `AVAILABLE`（BR-024/BR-024a）；7. 惰性失效判定与队列顺延**必须在同一事务内完成**（BR-025b）；8. 收缴罚款：仅 `LIBRARIAN`/`SYSTEM_ADMIN`，写入 `operator_id` 与 `operator_role`，状态 → `PAID`；重复收缴返回 400；9. **四项状态变更（借阅/副本/罚款/预约）在同一事务内**，任一失败全部回滚 |
| **验收标准** | ① TC-015~TC-021、TC-036 全部通过；② 罚款金额与示例表一致（如外文书超期 21 天 → 9.50 元）；③ 还书后副本 `RESERVED` 且队首 `READY`；④ 事务回滚验证通过 |
| **建议测试** | `tests/integration/test_return.py`：TC-015、TC-016、TC-017、TC-018、TC-019、TC-036 + 收缴 |

---

## TASK-014 实现续借

| 项 | 内容 |
|---|---|
| **任务目标** | 实现读者自助续借 |
| **输入规格** | `03-use-cases.md` UC-007；`02-requirements.md` FR-018、BR-015~BR-019；`15-test-plan.md` TC-035 |
| **允许修改** | `backend/app/presentation/routers/circulation_router.py`、`backend/app/application/services/circulation_service.py`、`backend/tests/integration/test_renew.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 借阅人本人或馆员可续借；非本人且非馆员 → 403；2. 最多 2 次、每次 +7 天、与读者类型无关（BR-015）；3. 已超期不可续借（BR-016）；4. 额度超额不可续借（BR-017）；5. **存在他人预约不构成禁止续借的条件**（BR-018——注意不要误加此限制）；6. 续借不额外占用额度（BR-019）；7. 判定逻辑使用 `RenewalService`，不在应用服务里写条件分支 |
| **验收标准** | ① TC-035 通过（含 4 个边界）；② `renew_count` 与 `due_at` 同步更新；③ 有预约时仍可续借 |
| **建议测试** | `tests/integration/test_renew.py`：TC-035 + 有预约时续借成功 |

---

## TASK-015 实现预约

| 项 | 内容 |
|---|---|
| **任务目标** | 实现预约、取消预约与预约状态查询 |
| **输入规格** | `03-use-cases.md` UC-005/UC-006；`12-sequence-reserve-book.md`；`09-design-model.md` §4；`15-test-plan.md` TC-025~TC-030 |
| **允许修改** | `backend/app/presentation/routers/reservation_router.py`、`presentation/schemas/reservation_schemas.py`、`backend/app/application/services/reservation_service.py`、`backend/tests/integration/test_reservation.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 预约人取自 **JWT 身份**，不接受请求体中的 `reader_id`（BR-039）；2. 仅当标题下**所有副本均不可借**时才可预约（BR-020）；3. 队列上限 **5 人**（BR-022）；4. 同一读者对同一标题只能有一个有效预约（BR-023）；5. 按 `created_at` 升序排队（BR-021）；6. 有效期 7 天：`ACTIVE` 自 `created_at` 起算，`READY` 自 `ready_at` 起算（BR-025）；7. **`ACTIVE` 与 `READY` 均可取消**（BR-025a）；8. 取消后若持有 `RESERVED` 副本，**转交下一位**并保持 `RESERVED`，队列空才释放为 `AVAILABLE`（BR-024a）；9. 返回排队位置 |
| **验收标准** | ① TC-025~TC-030 通过；② 排队位置与创建时间一致；③ 取消后副本仍为 `RESERVED`（若队列非空） |
| **建议测试** | `tests/integration/test_reservation.py`：TC-025、TC-026、TC-027、TC-028、TC-029、TC-030 |

---

## TASK-016 实现查询与统计

| 项 | 内容 |
|---|---|
| **任务目标** | 实现图书查询、借阅信息查询、罚款查询、预约查询与馆藏统计 |
| **输入规格** | `14-api-spec.md` §4.1、§5.5、§5.6、§5.8、§6.3、§8；`09-design-model.md` §5 |
| **允许修改** | `backend/app/presentation/routers/query_router.py`、`presentation/schemas/query_schemas.py`、`backend/app/application/services/query_service.py`、`backend/tests/integration/test_query.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. **查询不经领域层**，`QueryService` 经 Repository 直接组装 DTO（`08` §1 已披露此设计）；2. 读者只能查本人；馆员与管理员可查任意读者（BR-039）；越权 → 403；3. 借阅信息返回 `current`/`history`/`overdue` 三段，`OVERDUE` 为**派生状态**（由 `due_at` 与当前时刻判定，不落库）；4. 已软删除的记录**不出现在结果中**（BR-037），仅系统管理员可查看已删记录；5. 分页参数 `page`/`page_size` 生效，`page_size` 上限 100 |
| **验收标准** | ① TC-022、TC-023、TC-024 通过；② 超期项标记正确；③ 越权访问返回 403；④ 分页边界正确 |
| **建议测试** | `tests/integration/test_query.py`：TC-022、TC-023、TC-024 + 分页与软删除过滤 |

---

## TASK-017 实现权限体系与规则维护

| 项 | 内容 |
|---|---|
| **任务目标** | 补全全局权限守卫与规则查询/维护接口 |
| **输入规格** | `14-api-spec.md` §7 + §1.2 权限矩阵；`03-use-cases.md` UC-213/UC-214/UC-215；`02-requirements.md` FR-027~FR-029、BR-049 |
| **允许修改** | `backend/app/presentation/routers/policy_router.py`、`presentation/schemas/policy_schemas.py`、`backend/app/application/services/policy_service.py`、`backend/app/main.py`（异常处理器）、`backend/tests/integration/test_policy.py`、`backend/tests/integration/test_permissions.py` |
| **禁止修改** | `backend/app/domain/**`、`specs/**` |
| **实现要求** | 1. 实现全局异常处理器，将 6 类异常统一映射为 `ErrorResponse`（`09-design-model.md` §10）；2. 规则查询对所有登录用户开放（读者需知晓本人额度）；3. 规则维护仅 `SYSTEM_ADMIN`（BR-041）；4. 规则**存数据库可在线维护**（BR-049），修改后立即生效于新业务，**不追溯**已有记录（BR-050）；5. 数值校验：`max_borrow_count ≥ 1`、`borrow_days ≥ 1`、`daily_price ≥ 0`、`grace_days ≥ 0`、`max_amount ≥ 0`；6. 馆藏统计接口返回按状态与类型分组的副本数 |
| **验收标准** | ① TC-031、TC-032 通过（越权矩阵全绿）；② 规则修改后新借阅按新规则计算；③ 异常响应体格式与 `14` §1.3 一致 |
| **建议测试** | `tests/integration/test_permissions.py`：TC-031、TC-032；`test_policy.py`：规则维护与生效 |

---

## TASK-018 完善测试与分层校验

| 项 | 内容 |
|---|---|
| **任务目标** | 补齐测试覆盖并执行分层与规格约束校验 |
| **输入规格** | `15-test-plan.md` 全文；`08-package-diagram.md` §2 依赖规则 |
| **允许修改** | `backend/tests/**`、`backend/pytest.ini` |
| **禁止修改** | `backend/app/**`（若发现代码问题，**回到对应任务修复**）、`specs/**` |
| **实现要求** | 1. 对照 `15-test-plan.md` 逐条核对覆盖情况，列出已覆盖与未覆盖清单；2. 补充未覆盖用例（含 TC-020b 单元测试组）；3. 执行 `15` §5 的 5 项通过标准；4. 连续两次全量运行验证可重复性；5. 输出测试覆盖分析报告 |
| **验收标准** | ① 36 个测试用例全部实现且通过；② 5 项通过标准全绿；③ 两次运行结果一致；④ 输出覆盖分析 |
| **建议测试** | `pytest -v`；分层检查命令见 §0.2 |

---

## 附录 A：任务与实验要求对照

| 实验二建议的任务顺序 | 本文件任务 | 判定 |
|---|---|---|
| 初始化项目结构 | TASK-001 | ✅ |
| 实现领域实体 | TASK-002、TASK-003、TASK-004 | ✅ 拆为枚举值对象 / 实体 / ORM 与 Mapper |
| 实现 Repository | TASK-005 | ✅ |
| 实现借阅规则策略 | TASK-007 | ✅ |
| 实现罚款规则策略 | TASK-008 | ✅ |
| 实现读者和借阅证管理 | TASK-009、TASK-010 | ✅ |
| 实现图书标题和馆藏管理 | TASK-011 | ✅ 未合并，满足「不得过大」约束 |
| 实现借书 | TASK-012 | ✅ |
| 实现还书 | TASK-013 | ✅ |
| 实现预约 | TASK-015 | ✅ |
| 实现查询 | TASK-016 | ✅ |
| 实现管理员权限 | TASK-017 | ✅ |
| 完善测试 | TASK-018 | ✅ |
| （本文件补充）实现领域服务 | TASK-006 | ✅ 保障借书/还书的判定逻辑有落点 |
| （本文件补充）实现续借 | TASK-014 | ✅ 实验要求覆盖 |

## 附录 B：每个任务完成后的固定动作

```bash
# 1. 跑测试
cd backend && pytest -v

# 2. 跑分层红线检查（§0.2）
grep -rn "fastapi\|sqlalchemy" backend/app/domain/ && echo "❌ 违规" || echo "✅ 通过"

# 3. 确认未触碰规格
git status --short specs/     # 期望：无输出

# 4. 提交（commit message 格式：英文标头 + 中文描述）
git add backend/
git commit -m "feat: complete TASK-0XX <英文描述>"
```

---

## 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|---|---|---|---|
| v1.0 | 2026-09-20 | 初版制定。18 个编码任务，每个含目标、输入规格、允许/禁止修改文件、实现要求、验收标准、建议测试；含分层红线自检命令、任务依赖图与实验要求对照表。 | Agent 起草 |
