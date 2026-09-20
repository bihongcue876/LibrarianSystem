# 详细设计模型（Design Model）

> **文档编号**：`specs/09-design-model.md`
> **制定依据**：`02-requirements.md`、`03-use-cases.md`、`05-domain-model.md`、`07-architecture.md`、`08-package-diagram.md`、`13-database-design.md`
> **版本**：v1.0
> **日期**：2026-09-20
>
> **本文件与 `05-domain-model.md` 的分工**：`05` 是**问题域模型**（只含实体、值对象、领域服务、策略对象，明确排除 Controller / Repository / DTO）；本文件是**解决方案域模型**，把领域模型落到分层架构上，补齐 `05` 有意排除的设计元素——Controller 入口、应用服务、Repository 接口、DTO、异常与事务边界。
>
> **本文件不做的事**：不写代码、不定义接口的完整字段清单（那是 `14-api-spec.md`）、不定义测试用例（那是 `15-test-plan.md`）。

---

## 1. 设计类总览

### 1.1 分层类清单

| 层 | 类别 | 数量 | 清单 |
|---|---|:---:|---|
| 表现层 | Controller（路由模块） | 7 | `auth_router`、`card_router`、`catalog_router`、`circulation_router`、`reservation_router`、`query_router`、`policy_router` |
| 表现层 | DTO（Pydantic Schema） | 24 | 见 §5 |
| 表现层 | 依赖注入与鉴权守卫 | 1 | `dependencies.py` |
| 应用层 | Application Service | 7 | `AuthService`、`CardService`、`CatalogService`、`CirculationService`、`ReservationService`、`QueryService`、`PolicyService` |
| 应用层 | Repository 接口（Port） | 7 | `ReaderRepository`、`CardRepository`、`CatalogRepository`、`LoanRepository`、`ReservationRepository`、`FineRepository`、`PolicyRepository` |
| 应用层 | 事务边界 | 1 | `UnitOfWork` |
| 领域层 | 实体 | 14 | 见 `05-domain-model.md` §1.2 |
| 领域层 | 值对象 / 枚举 | 12 | 见 `05-domain-model.md` §1.2 |
| 领域层 | 领域服务 | 3 | `BorrowEligibilityService`、`RenewalService`、`ReservationQueueService` |
| 领域层 | 策略对象 | 2 | `BorrowPolicy`、`FineRule` |
| 领域层 | 工厂 | 2 | `ReaderFactory`、`LibraryItemFactory` |
| 基础设施层 | Repository 实现 | 7 | `SqlAlchemy*Repository` |
| 基础设施层 | Mapper | 7 | `*Mapper` |
| 基础设施层 | ORM 模型 | 7 组 | 映射 11 张表 |

### 1.2 应用服务职责表

| 应用服务 | 职责一句话 | 主要委托的领域对象 | 依赖 Repository 数 |
|---|---|---|:---:|
| `AuthService` | 认证与账号生命周期（登录、注册、员工账号增删、密码重置） | `Reader`、`Librarian`、`SystemAdmin`、`ReaderFactory` | 1 |
| `CardService` | 借阅证的签发、注销、恢复、挂失解挂 | `BorrowCard`、`CardNumber` | 2 |
| `CatalogService` | 图书标题与馆藏副本的增删改 | `BookTitle`、`LibraryItem`、`Barcode`、`Isbn`、`LibraryItemFactory` | 1 |
| `CirculationService` | 借书、还书、续借、罚款收缴——**跨模块编排** | `BorrowEligibilityService`、`RenewalService`、`ReservationQueueService`、`BorrowPolicy`、`FineRule`、`Loan`、`FineRecord` | 7 |
| `ReservationService` | 预约创建、取消、查询、到书处理 | `ReservationQueueService`、`Reservation` | 3 |
| `QueryService` | 只读查询与统计，**不经过领域层** | 无（经 Repository 直接组装 DTO） | 6 |
| `PolicyService` | 借阅规则与罚款规则的查询与维护 | `BorrowPolicy`、`FineRule` | 1 |

**关键分工原则**：应用服务只做「取数据 → 调领域对象 → 落库 → 组装 DTO」，**不做业务判定**。所有判定逻辑下沉到领域层（领域服务或策略对象）。这是宪法第八条（业务规则集中）在应用层的体现。

### 1.3 设计类命名对照（实验文档建议名 ↔ 本设计名）

实验文档的顺序图 Prompt 中使用了若干建议类名，本项目的实际类名与之对应关系如下（`14`、`15`、`16` 及顺序图统一使用**本设计名**）：

| 实验文档建议名 | 本设计名 | 说明 |
|---|---|---|
| `LibrarianController` | `circulation_router` 的借还接口 | 本项目路由按**限界上下文**划分而非按角色划分，图书管理员与系统管理员共用同一路由模块，权限由 `require_role` 守卫区分 |
| `ReaderController` | `circulation_router`（查询）+ `reservation_router` | 读者的自助操作分散在查询与预约两个路由模块 |
| `BorrowPolicyService` | `BorrowPolicy`（策略对象）+ `PolicyService`（维护入口） | 本项目把「规则数值查询」放在策略对象、「规则维护」放在应用服务，不合并为一个 Service |
| `FineRuleService` | `FineRule`（策略对象）+ `PolicyService` | 同上 |
| `FineService` | `CirculationService` 的还书与收缴方法 | 罚款**不是独立的操作入口**，由还书自动触发或流通窗口收缴，故不单设应用服务（`08-package-diagram.md` §1 已说明） |

---

## 2. 用例设计：UC-101 办理借书

### 2.1 设计要素

| 设计要素 | 内容 |
|---|---|
| **用例** | UC-101 办理借书（`03-use-cases.md`） |
| **参与者** | 主要：图书管理员；次要：读者（借阅证持有者，不直接操作） |
| **Controller 入口** | `circulation_router.py` → `POST /api/circulation/borrow`（`borrow_book`） |
| **Application Service** | `CirculationService.borrow_book(request, operator)` |
| **Domain Service** | `BorrowEligibilityService.check_eligibility(...)`（六项校验，纯函数式） |
| **Entity / Aggregate** | 聚合根：`Loan`（新建）、`LibraryItem`（状态变更）；只读：`Reader`、`BorrowCard`、`Reservation`、`FineRecord` |
| **Repository** | `ReaderRepository`（读）、`CardRepository`（读借阅证）、`CatalogRepository`（读副本 + 写状态）、`LoanRepository`（写借阅记录）、`ReservationRepository`（读预约以计算额度）、`FineRepository`（读未缴罚款）、`PolicyRepository`（读规则） |
| **DTO** | 请求：`BorrowBookRequest`；响应：`BorrowBookResponse`；复用：`LoanSummary`、`ErrorResponse` |
| **异常** | `ForbiddenError`（非馆员角色，403）、`ValidationError`（借阅证不存在或状态非 `ACTIVE` → `CARD_INVALID`）、`BusinessRuleError`（超额 `BORROW_LIMIT_EXCEEDED`、超期未还 `OVERDUE_LOAN_EXISTS`、有欠款 `UNPAID_FINE_EXISTS`、副本不可借 `ITEM_NOT_AVAILABLE`）——**四类业务规则失败均为 HTTP 400**（依 `02` FR-016 验收标准 2） |
| **事务边界** | 应用服务层；范围 = 读校验链 + 创建 `Loan` + 更新 `LibraryItem.status`；提交点 = 全部成功后 |

### 2.2 处理步骤

| # | 步骤 | 执行者 | 说明 |
|:---:|---|---|---|
| 1 | 接收请求，校验角色 | `circulation_router` + `dependencies.require_role` | 仅 `LIBRARIAN` / `SYSTEM_ADMIN` 可调用 |
| 2 | 开启事务 | `CirculationService` + `UnitOfWork` | 事务边界起点 |
| 3 | 按借阅证号取 `BorrowCard`，按条码取 `LibraryItem` | `CardRepository`、`CatalogRepository` | 任一不存在：借阅证 → `CARD_INVALID`（400），条码 → `ITEM_NOT_AVAILABLE`（400） |
| 4 | 按 `reader_id` 取读者 | `ReaderRepository` | 读者已软删除 → `NotFoundError` |
| 5 | 聚合校验数据 | `CirculationService` | 取读者的未归还借阅、有效预约、未缴罚款，取当前 `BorrowPolicy` |
| 6 | **六项校验（固定顺序）** | `BorrowEligibilityService` | 权限 → 借阅证 → 数量 → 超期 → 罚款 → 副本。**遇到第一个失败即抛异常，不累积** |
| 7 | 创建 `Loan`，快照 `due_at` | `Loan.create(reader, item, policy, librarian)` | 借期由 `BorrowPolicy.days_for(reader_type)` 决定，写入时刻即快照（BR-050：规则修改不追溯） |
| 8 | 更新副本状态 | `LibraryItem.mark_borrowed()` | `AVAILABLE` → `BORROWED` |
| 9 | 持久化 | `LoanRepository.add`、`CatalogRepository.update` | |
| 10 | 提交事务 | `UnitOfWork.commit` | 全部成功才提交 |
| 11 | 组装响应 | `CirculationService` → `BorrowBookResponse` | 返回借阅记录摘要 + 应还日期 |

### 2.3 类职责说明

| 类 | 职责 | 不负责 |
|---|---|---|
| `circulation_router.borrow_book` | 解析请求体、注入当前账号、调用应用服务、返回 HTTP 响应 | 任何业务判定 |
| `CirculationService` | 事务编排、数据聚合、调用领域服务与实体、组装 DTO | 判定规则本身 |
| `BorrowEligibilityService` | 六项借阅资格判定，返回判定结果 | 修改任何实体状态、访问数据库 |
| `Loan` | 承载借阅生命周期（创建、续借、归还、超期判定） | 判定读者是否有资格借 |
| `LibraryItem` | 承载副本状态机 | 知晓借阅人是谁 |
| `Read\*Repository` | 按标识取单个聚合 / 按条件取集合 | 业务判定、事务提交 |

---

## 3. 用例设计：UC-102 办理还书

### 3.1 设计要素

| 设计要素 | 内容 |
|---|---|
| **用例** | UC-102 办理还书（`03-use-cases.md`） |
| **参与者** | 主要：图书管理员；次要：读者（不直接操作，无需出示借阅证） |
| **Controller 入口** | `circulation_router.py` → `POST /api/circulation/return`（`return_book`） |
| **Application Service** | `CirculationService.return_book(request, operator)` |
| **Domain Service** | `ReservationQueueService`（还书后的副本交接与队列顺延） |
| **Entity / Aggregate** | 聚合根：`Loan`（状态变更）、`LibraryItem`（状态变更）、`FineRecord`（条件新建）、`Reservation`（队首状态变更） |
| **Repository** | `CatalogRepository`、`LoanRepository`、`FineRepository`、`ReservationRepository`、`PolicyRepository` |
| **DTO** | 请求：`ReturnBookRequest`；响应：`ReturnBookResponse`（含罚款金额与预约交接结果）；复用：`FineSummary` |
| **异常** | `ForbiddenError`（非馆员角色）、`NotFoundError`（条码不存在 / 无未归还借阅记录） |
| **事务边界** | 应用服务层；范围 = 更新 `Loan` + 更新 `LibraryItem` + 条件创建 `FineRecord` + 预约队列顺延与副本交接；提交点 = 全部成功后 |

### 3.2 处理步骤

| # | 步骤 | 执行者 | 说明 |
|:---:|---|---|---|
| 1 | 校验角色 | `circulation_router` + `require_role` | **仅凭馆藏条码，不要求借阅证**（UC-102 明确） |
| 2 | 开启事务 | `UnitOfWork` | |
| 3 | 按条码取副本 | `CatalogRepository` | 不存在 → `NotFoundError`（非本馆藏书） |
| 4 | 查该副本的未归还 `Loan` | `LoanRepository.find_active_by_item(item_id)` | 无记录 → `NotFoundError` |
| 5 | 计算超期天数与罚款 | `Loan.overdue_days(now)` + `FineRule.calculate_fine(item_type, overdue_days)` | 见 §8 UC-102a 详细设计 |
| 6 | 更新借阅记录 | `Loan.return_item(now)` | `status` → `RETURNED`，写入 `returned_at` |
| 7 | 条件生成罚款记录 | `FineRecord.create(loan, item_type, returned_at, fine_rule)` | **仅当罚款金额 > 0** 时创建（BR-029、BR-030） |
| 8 | 决定副本去向 | `ReservationQueueService` | 该标题有有效预约队列 → 队首置 `READY`，副本置 `RESERVED`（BR-024a）；无队列 → 副本置 `AVAILABLE` |
| 9 | 触发队列顺延与惰性失效判定 | `ReservationQueueService.dequeue_expired` + `peek` | 同事务内完成（BR-025b） |
| 10 | 持久化 | `LoanRepository`、`CatalogRepository`、`FineRepository`、`ReservationRepository` | |
| 11 | 提交事务 | `UnitOfWork.commit` | |
| 12 | 组装响应 | `CirculationService` | 返回归还结果 + 罚款（如有）+ 副本去向 |

### 3.3 类职责说明

| 类 | 职责 | 不负责 |
|---|---|---|
| `CirculationService.return_book` | 编排还书的四项状态变更 | 计算罚款公式、判定队列 |
| `Loan.return_item` / `overdue_days` | 自身状态与超期天数计算 | 罚款单价（委托 `FineRule`） |
| `FineRule` | 按 `item_type` 查表给出单价、宽限天数、封顶金额并计算 | 创建 `FineRecord` |
| `ReservationQueueService` | 队列语义：队首识别、失效清理、顺延与副本交接 | 修改罚款、借阅记录 |

---

## 4. 用例设计：UC-005 预约图书

### 4.1 设计要素

| 设计要素 | 内容 |
|---|---|
| **用例** | UC-005 预约图书（`03-use-cases.md`） |
| **参与者** | 主要：读者 |
| **Controller 入口** | `reservation_router.py` → `POST /api/reservations`（`create_reservation`） |
| **Application Service** | `ReservationService.create_reservation(request, current_account)` |
| **Domain Service** | `ReservationQueueService.can_reserve(title, existing)` + `enqueue(...)` |
| **Entity / Aggregate** | 聚合根：`Reservation`（新建）；只读：`BookTitle`、`Reader` |
| **Repository** | `ReaderRepository`、`CatalogRepository`（读 `BookTitle`）、`ReservationRepository`、`LoanRepository`（判断副本可借性） |
| **DTO** | 请求：`CreateReservationRequest`；响应：`ReservationResponse`（含排队位置） |
| **异常** | `ForbiddenError`（读者访问他人数据）、`NotFoundError`（读者/标题不存在）、`ConflictError`（重复预约）、`BusinessRuleError`（有可借副本无需预约 / 队列已满 5 人） |
| **事务边界** | 应用服务层；范围 = 校验队列 + 创建 `Reservation`；提交点 = 成功后 |

### 4.2 处理步骤

| # | 步骤 | 执行者 | 说明 |
|:---:|---|---|---|
| 1 | 校验身份 | `dependencies.get_current_account` | 读者只能为**本人**预约（BR-039：不信任请求体中的 `reader_id`） |
| 2 | 开启事务 | `UnitOfWork` | |
| 3 | 取读者与图书标题 | `ReaderRepository`、`CatalogRepository` | 任一不存在 → `NotFoundError`（404） |
| 4 | 判断标题可预约性 | `BookTitle.can_be_reserved()` + `ReservationQueueService.can_reserve(...)` | 所有副本均不可借才可预约（BR-020）；无标题下无副本时不可预约 |
| 5 | 查重 | `ReservationQueueService.can_reserve(...)` | 同一读者对同一标题不得有多个有效预约（BR-023）→ `ConflictError` |
| 6 | 校验队列容量 | `ReservationQueueService.enqueue(...)` | 队列上限 5 人（BR-022）→ `BusinessRuleError` |
| 7 | 创建预约 | `Reservation.create(reader, title)` | `status` = `ACTIVE`，`created_at` 决定排队顺序（BR-021，**不依赖自增主键**） |
| 8 | 持久化 | `ReservationRepository.add` | |
| 9 | 提交事务 | `UnitOfWork.commit` | |
| 10 | 组装响应 | `ReservationService` | 返回预约信息 + 当前排队位置 |

### 4.3 类职责说明

| 类 | 职责 | 不负责 |
|---|---|---|
| `ReservationService` | 身份归属校验、事务编排、排队位置查询 | 队列规则本身 |
| `ReservationQueueService` | 队列语义：上限校验、队首识别、位置计算、失效清理与顺延 | 持久化 |
| `Reservation` | 承载预约生命周期（`ACTIVE` → `READY` → `EXPIRED` / `CANCELLED`，共 4 态） | 知晓整个队列 |
| `BookTitle` | 题录信息与可借性判定 | 知晓副本被谁借走 |

---

## 5. 用例设计：UC-004 / UC-103 查询借阅信息

### 5.1 设计要素

| 设计要素 | 内容 |
|---|---|
| **用例** | UC-004 查询借阅信息（读者自助）、UC-103 查询读者借阅信息（馆员代理查询） |
| **参与者** | 读者 / 图书管理员 |
| **Controller 入口** | `circulation_router.py` → `GET /api/readers/{reader_id}/loans`；`GET /api/me/loans` |
| **Application Service** | `QueryService.get_reader_loans(reader_id, operator, filters)` |
| **Domain Service** | **无**——纯查询不涉及业务规则判定（`08-package-diagram.md` §1：查询不产生领域行为） |
| **Entity / Aggregate** | 无（不经领域层，直接由 Repository 组装 DTO） |
| **Repository** | `LoanRepository`（借阅记录）、`CatalogRepository`（副本与题录信息）、`ReaderRepository`（读者基本信息）、`FineRepository`（未缴罚款） |
| **DTO** | 请求：查询参数 `LoanQuery`；响应：`ReaderLoansResponse`（含 `current`、`history`、`overdue` 三段）、`LoanDetail` |
| **异常** | `ForbiddenError`（读者查询他人数据）、`NotFoundError`（读者不存在） |
| **事务边界** | **只读，无写事务**（可用只读连接，不显式提交） |

### 5.2 处理步骤

| # | 步骤 | 执行者 | 说明 |
|:---:|---|---|---|
| 1 | 解析当前账号与目标 `reader_id` | `dependencies.get_current_account` | |
| 2 | **归属校验** | `QueryService` | 读者只能查本人；馆员与管理员可查任意读者（BR-039）→ 越权 `ForbiddenError`（403） |
| 3 | 校验读者存在 | `ReaderRepository` | 不存在或已软删除 → `NotFoundError`（404） |
| 4 | 取借阅记录 | `LoanRepository.find_by_reader(reader_id)` | 一次取回，内存分组 |
| 5 | 标记超期 | `Loan.is_overdue(now)`（领域方法） | `OVERDUE` 为**派生状态**，不落库（`05-domain-model.md` §5.3） |
| 6 | 组装三段结果 | `QueryService` | 当前借阅 / 历史借阅 / 超期列表 |
| 7 | 附未缴罚款汇总 | `FineRepository.find_unpaid_by_reader` | 供馆员在窗口判断是否可继续借书 |
| 8 | 返回响应 | 不提交事务 | |

### 5.3 类职责说明

| 类 | 职责 | 不负责 |
|---|---|---|
| `circulation_router` 查询端点 | 参数解析、权限注入 | 归属校验（在应用服务） |
| `QueryService` | 归属校验、跨模块数据组装、DTO 拼装 | 业务判定、状态变更 |
| Repository（只读方法） | 按条件查询与投影 | 组装业务语义 |

> **为什么查询不经领域层**：纯查询没有业务规则需要守卫，强行绕行领域层只会产生「为了分层而分层」的空转。这条设计选择已在 `08-package-diagram.md` §1 披露，属**有意为之**。

---

## 6. 用例设计：UC-201 办理借阅证

### 6.1 设计要素

| 设计要素 | 内容 |
|---|---|
| **用例** | UC-201 办理借阅证（`03-use-cases.md`） |
| **参与者** | 主要：系统管理员 |
| **Controller 入口** | `card_router.py` → `POST /api/admin/borrow-cards`（`issue_card`） |
| **Application Service** | `CardService.issue_card(request, operator)` |
| **Domain Service** | 无（校验逻辑内聚在 `BorrowCard` 与 `CardNumber` 值对象） |
| **Entity / Aggregate** | 聚合根：`BorrowCard`（新建）；只读：`Reader` |
| **Repository** | `CardRepository`（查重 + 写入）、`ReaderRepository` |
| **DTO** | 请求：`IssueCardRequest`；响应：`BorrowCardResponse` |
| **异常** | `ForbiddenError`（非系统管理员）、`NotFoundError`（读者不存在）、`ConflictError`（已有有效借阅证） |
| **事务边界** | 应用服务层；范围 = 校验 → 生成证号 → 创建 `BorrowCard`；提交点 = 成功后 |

### 6.2 处理步骤

| # | 步骤 | 执行者 | 说明 |
|:---:|---|---|---|
| 1 | 校验角色 | `require_role` | 仅 `SYSTEM_ADMIN`（BR-041） |
| 2 | 开启事务 | `UnitOfWork` | |
| 3 | 校验读者存在 | `ReaderRepository` | 不存在或已软删除 → `NotFoundError` |
| 4 | 校验一证限制 | `CardRepository.find_active_by_reader(reader_id)` | 已有 `ACTIVE`/`SUSPENDED` 证 → `ConflictError`（BR-003，`CANCELLED` 不计入） |
| 5 | 生成证号 | `CardNumber.generate(year, sequence)` | 格式 `CARD` + 4 位年份 + 6 位序号，如 `CARD2026000001`；序号由 `CardRepository.next_sequence()` 提供 |
| 6 | 创建借阅证 | `BorrowCard.issue(reader, admin)` | `status` = `ACTIVE`，记录 `issued_at` / `issued_by` |
| 7 | 持久化 | `CardRepository.add` | 证号唯一约束由数据库保证（`13` §4.2） |
| 8 | 提交事务 | `UnitOfWork.commit` | |
| 9 | 组装响应 | `CardService` | 返回证号与有效期信息 |

### 6.3 类职责说明

| 类 | 职责 | 不负责 |
|---|---|---|
| `CardService` | 权限与业务校验编排、证号序列获取 | 证号格式规则 |
| `CardNumber` | 证号格式校验与生成（正则 `^CARD\d{4}\d{6}$`） | 数据库唯一性 |
| `BorrowCard` | 状态机守卫（`issue`/`cancel`/`restore`/`suspend`/`resume`） | 判定读者是否有资格持证 |

---

## 7. 用例设计：UC-208 添加图书标题 / UC-210 添加馆藏副本

### 7.1 设计要素（UC-208 添加图书标题）

| 设计要素 | 内容 |
|---|---|
| **Controller 入口** | `catalog_router.py` → `POST /api/admin/book-titles`（`add_book_title`） |
| **Application Service** | `CatalogService.add_book_title(request, operator)` |
| **Domain Service** | 无 |
| **Entity / Aggregate** | 聚合根：`BookTitle`（新建） |
| **Repository** | `CatalogRepository`（ISBN 查重 + 写入） |
| **DTO** | 请求：`AddBookTitleRequest`；响应：`BookTitleResponse` |
| **异常** | `ForbiddenError`（非系统管理员）、`ConflictError`（ISBN 重复）、`ValidationError`（ISBN 格式非法 / `item_type` 不在枚举内） |
| **事务边界** | 应用服务层；范围 = 校验 → 创建 `BookTitle`；提交点 = 成功后 |

**处理步骤**：

1. 校验角色（仅 `SYSTEM_ADMIN`）→ 2. 开启事务 → 3. 校验 ISBN 格式（`Isbn.normalize` + `Isbn.is_valid`）→ 4. 校验 `item_type` 在 `ItemType` 枚举内 → 5. ISBN 查重（**部分唯一索引**：仅校验活跃记录，`13` §4.1）→ 6. `BookTitle` 创建，`is_deleted = False` → 7. 持久化 → 8. 提交 → 9. 返回响应。

### 7.2 设计要素（UC-210 添加馆藏副本）

| 设计要素 | 内容 |
|---|---|
| **Controller 入口** | `catalog_router.py` → `POST /api/admin/library-items`（`add_library_item`） |
| **Application Service** | `CatalogService.add_library_item(request, operator)` |
| **Domain Service** | 无；类型分派由 `LibraryItemFactory` 承担 |
| **Entity / Aggregate** | 聚合根：`BookTitle`（添加副本，题录-副本组合关系）；新对象：`LibraryItem` 子类 |
| **Repository** | `CatalogRepository`（读题录 + 条码查重 + 写入副本） |
| **DTO** | 请求：`AddLibraryItemRequest`；响应：`LibraryItemResponse` |
| **异常** | `ForbiddenError`（非系统管理员）、`NotFoundError`（题录不存在）、`ConflictError`（条码重复） |
| **事务边界** | 应用服务层；范围 = 校验 → 生成条码 → 创建副本；提交点 = 成功后 |

**处理步骤**：

1. 校验角色（仅 `SYSTEM_ADMIN`）→ 2. 开启事务 → 3. 取 `BookTitle`，不存在 → `NotFoundError` → 4. 生成条码（`Barcode.generate(sequence)`，格式 `BC` + 8 位序号）并查重 → 5. 由 `LibraryItemFactory.create(title, barcode, ...)` 按题录的 `item_type` 分派到 `Book` / `Magazine` / `Thesis` 子类（Factory 模式落点）→ 6. 状态置 `AVAILABLE` → 7. 持久化（单表继承，写入 `library_items` 表 + `item_type` 判别列）→ 8. 提交 → 9. 返回响应。

### 7.3 类职责说明

| 类 | 职责 | 不负责 |
|---|---|---|
| `CatalogService` | 校验编排、条码序列获取、持久化调用 | 类型分派（委托工厂） |
| `LibraryItemFactory` | 按 `item_type` 创建正确的 `LibraryItem` 子类 | 校验业务规则 |
| `BookTitle` | 题录信息 + `addItem()` / `availableItems()` / `canBeReserved()` | 知晓副本的借阅人 |
| `LibraryItem` | 副本状态机与条码 | 题录信息（`item_type` 为受控冗余，自题录同步） |
| `Isbn` / `Barcode` | 格式校验与生成 | 唯一性（由数据库约束） |

---

## 8. 用例设计：UC-102a 计算超期罚款

### 8.1 设计要素

| 设计要素 | 内容 |
|---|---|
| **用例** | UC-102a 计算超期罚款（被 UC-101 与 UC-102 **include**，`04-use-case-model.md` 图 5） |
| **参与者** | 无直接参与者（内部用例，由还书流程触发） |
| **Controller 入口** | **无独立入口**——随 `POST /api/circulation/return` 触发；查询入口：`GET /api/fines/{fine_id}` |
| **Application Service** | `CirculationService.return_book(...)` 内部调用；收缴另见 `collect_fine(...)` |
| **Domain Service** | 无（计算内聚在 `FineRule` 策略对象） |
| **Entity / Aggregate** | 聚合根：`FineRecord`（条件新建）；只读：`Loan` |
| **Repository** | `PolicyRepository`（读 `FineRule`）、`FineRepository`（写罚款记录）、`LoanRepository` |
| **DTO** | 请求：无（内部）；响应内嵌：`FineSummary`；独立查询：`FineDetail`；收缴请求：`CollectFineRequest` |
| **异常** | `ValidationError`（罚款记录不存在 / 重复收缴）、`ForbiddenError`（非馆员或管理员） |
| **事务边界** | **与还书同一事务**（不得拆开：罚款生成失败则还书回滚） |

### 8.2 计算规则（`FineRule` 策略对象）

```
overdue_days = max((returned_at - due_at).days, 0)
billed_days  = max(overdue_days - grace_days, 0)          # grace_days 默认 2
amount       = min(billed_days × daily_price, max_amount) # max_amount 默认 100.00
```

| itemType | dailyPrice | graceDays | maxAmount |
|---|---:|---:|---:|
| `CHINESE_BOOK` | 0.20 | 2 | 100.00 |
| `FOREIGN_BOOK` | 0.50 | 2 | 100.00 |
| `CHINESE_MAGAZINE` | 0.10 | 2 | 100.00 |
| `FOREIGN_MAGAZINE` | 0.20 | 2 | 100.00 |
| `THESIS` | 1.00 | 2 | 100.00 |

**金额精度**：全程使用 `Money` 值对象（内部 `Decimal` + `quantize(0.01)`），**禁止 `float`**（Q-04 裁定，`02-requirements.md` §7）。

### 8.3 处理步骤

| # | 步骤 | 执行者 | 说明 |
|:---:|---|---|---|
| 1 | 取超期天数 | `Loan.overdue_days(now)` | 由 `due_at` 与归还时刻计算 |
| 2 | 提前返回 | `CirculationService` | `overdue_days ≤ 0` → 不创建 `FineRecord` |
| 3 | 取规则 | `PolicyRepository.get_fine_rule(item_type)` | 按副本的 `item_type` 查表（非代码分支） |
| 4 | 计算计罚天数 | `FineRule.billed_days(overdue_days)` | 扣除宽限天数 |
| 5 | 计算金额 | `FineRule.calculate_fine(item_type, overdue_days)` → `Money` | 含封顶 |
| 6 | 创建罚款记录 | `FineRecord.create(loan, item_type, returned_at, fine_rule)` | **快照 `unit_price`**，使规则修改不追溯（BR-050） |
| 7 | 状态置 `UNPAID` | `FineRecord` | |
| 8 | 持久化 | `FineRepository.add` | |
| 9 | （另一次操作）收缴 | `CirculationService.collect_fine(...)` → `FineRecord.pay(operator)` | 记录 `operator_id` 与 `operator_role`，状态 → `PAID` |

### 8.4 类职责说明

| 类 | 职责 | 不负责 |
|---|---|---|
| `FineRule` | 按 `item_type` 查表给出单价/宽限/封顶并计算金额 | 创建记录、收缴 |
| `FineRecord` | 承载罚款生命周期（`UNPAID` → `PAID`）、快照单价 | 计算金额公式 |
| `Money` | 精度约束、封顶比较、加减乘运算 | 业务规则 |
| `Loan` | 提供超期天数 | 知晓罚款单价 |

---

## 9. DTO 清单

### 9.1 请求 DTO

| DTO | 所属路由 | 关键字段 |
|---|---|---|
| `LoginRequest` | `auth_router` | `username`、`password` |
| `RegisterReaderRequest` | `auth_router` | `username`、`password`、`name`、`department`、`reader_type` |
| `AddLibrarianRequest` | `auth_router` | `username`、`password`、`name` |
| `ResetPasswordRequest` | `auth_router` | `account_id`、`new_password`（Q-05：管理员重置） |
| `IssueCardRequest` | `card_router` | `reader_id` |
| `CancelCardRequest` / `RestoreCardRequest` / `SuspendCardRequest` | `card_router` | `card_id`、`reason`（可空） |
| `AddBookTitleRequest` | `catalog_router` | `title`、`author`、`isbn`、`publisher`、`publish_year`、`item_type`、`language` |
| `AddLibraryItemRequest` | `catalog_router` | `title_id`、`location`、`price`、`acquired_at` |
| `BorrowBookRequest` | `circulation_router` | `card_no`、`barcode` |
| `BorrowPreCheckRequest` | `circulation_router` | `card_no`、`barcode`（FR-015 预检查，不产生副作用） |
| `ReturnBookRequest` | `circulation_router` | `barcode` |
| `RenewLoanRequest` | `circulation_router` | `loan_id` |
| `CollectFineRequest` | `circulation_router` | `fine_id` |
| `CreateReservationRequest` | `reservation_router` | `title_id` |
| `UpdateBorrowPolicyRequest` | `policy_router` | `reader_type`、`max_borrow_count`、`borrow_days` |
| `UpdateFineRuleRequest` | `policy_router` | `item_type`、`daily_price`、`grace_days`、`max_amount` |

### 9.2 响应 DTO

| DTO | 说明 |
|---|---|
| `TokenResponse` | JWT Token、角色、账号 ID |
| `AccountResponse` | 账号基本信息 |
| `BorrowCardResponse` | 证号、状态、签发信息 |
| `BookTitleResponse` | 题录信息 + 可借副本数 |
| `LibraryItemResponse` | 条码、状态、位置 |
| `BorrowBookResponse` | 借阅 ID、应还日期、剩余额度 |
| `PreCheckResponse` | 六项校验结果列表（供借书前置确认） |
| `ReturnBookResponse` | 归还结果、罚款（如有）、副本去向（`AVAILABLE` / `RESERVED`） |
| `ReaderLoansResponse` | `current` / `history` / `overdue` 三段 |
| `LoanDetail` | 单条借阅详情 |
| `ReservationResponse` | 预约状态、排队位置、`ready_at` |
| `FineSummary` / `FineDetail` | 罚款金额、天数、状态 |
| `BorrowPolicyResponse` / `FineRuleResponse` | 规则当前值 |
| `CollectionStatsResponse` | 馆藏统计（FR-029） |
| `ErrorResponse` | 统一错误体（`code`、`message`、`detail`） |

---

## 10. 异常设计与 HTTP 映射

| 异常类 | 归属层 | HTTP | 典型触发 | 错误码示例 |
|---|---|:---:|---|---|
| `NotFoundError` | 领域 | 404 | 读者不存在、题录不存在、无未归还借阅、罚款记录不存在 | `READER_NOT_FOUND`、`TITLE_NOT_FOUND`、`LOAN_NOT_FOUND` |
| `ValidationError` | 领域 | 400 | 借阅证不存在或状态非 `ACTIVE`、参数非法 | `CARD_INVALID`、`INVALID_ISBN` |
| `BusinessRuleError` | 领域 | 400 | 超额、超期未还、欠款未清、副本不可借、队列满 | `BORROW_LIMIT_EXCEEDED`、`OVERDUE_LOAN_EXISTS`、`UNPAID_FINE_EXISTS`、`ITEM_NOT_AVAILABLE` |
| `ConflictError` | 领域 | 409 | 重复预约、重复办证、条码或 ISBN 重复 | `DUPLICATE_RESERVATION`、`CARD_ALREADY_EXISTS` |
| `ForbiddenError` | 应用 | 403 | 角色越权、读者访问他人数据 | `PERMISSION_DENIED` |
| `UnauthorizedError` | 应用 | 401 | 未登录、Token 过期 | `UNAUTHORIZED` |

**统一基类**：`DomainError`（领域层）+ `ApplicationError`（应用层），由 `main.py` 的全局异常处理器统一映射为 `ErrorResponse`。

> **状态码权威来源**：**以 `02-requirements.md` 各 FR 的验收标准为准**。本表是层级通用约定，具体接口若与 FR 冲突（如 FR-016 把借书业务规则失败规定为 400），以 FR 为准。`07-architecture.md` §6.2 与本表含义相同，已加同样说明。

**借书校验顺序决定错误码**：六项校验「权限 → 借阅证 → 数量 → 超期 → 罚款 → 副本」**遇到第一个失败即返回**，不累积多个错误（UC-101 明确，`07-architecture.md` §6.2）。

---

## 11. 事务边界汇总

| 操作 | 事务范围 | 提交点 | 跨模块写入 |
|---|---|---|---|
| 办理借书 | 读校验链 → 创建 `Loan` → 更新副本状态 | 全部成功后 | 借阅 + 馆藏 |
| 办理还书 | 更新 `Loan` → 更新副本 → 条件创建 `FineRecord` → 预约队列顺延与副本交接 | 全部成功后 | 借阅 + 馆藏 + 罚款 + 预约 |
| 续借 | 校验 → 更新 `due_at` → 递增 `renew_count` | 成功后 | 借阅 |
| 预约图书 | 校验队列 → 创建 `Reservation` | 成功后 | 预约 |
| 取消预约 | 更新状态 → 条件顺延与副本交接 | 成功后 | 预约 + 馆藏 |
| 办理借阅证 | 校验 → 生成证号 → 创建 `BorrowCard` | 成功后 | 借阅证 |
| 添加题录 / 副本 | 校验 → 创建 | 成功后 | 馆藏 |
| 收缴罚款 | 校验 → `FineRecord.pay` | 成功后 | 罚款 |
| 规则维护 | 校验 → 更新规则行 | 成功后 | 规则 |
| 全部查询 | **无写事务** | 不提交 | — |

**并发控制**：依赖 SQLite 写串行化 + 事务原子性，**不引入乐观锁**（ADR-03）。预约队列的并发安全由应用层事务保证，领域服务本身不处理锁（`05-domain-model.md` §6.3）。

---

## 12. 设计模式使用位置

| 模式 | 落点 | 解决的问题 |
|---|---|---|
| **MVC** | `presentation/routers`（Controller）+ `schemas`（View 数据）+ `domain`（Model） | 表现与业务分离；路由函数不含业务逻辑 |
| **Service Layer** | `application/services/*` | 定义事务边界与用例级编排，避免路由直接操作多个 Repository |
| **Repository** | `application/ports/*` 定义接口，`infrastructure/repositories/*` 实现 | 持久化细节不泄漏到领域层；可替换为内存实现做单测 |
| **Strategy** | `domain/policies/BorrowPolicy`、`FineRule` | 读者类型差异与借出物类型差异通过**查表**表达，规则存数据库可在线维护（BR-049），而非 `if readerType == ...` 分支 |
| **Factory** | `domain/factories/ReaderFactory`（按 `reader_type` 造读者子类）、`LibraryItemFactory`（按 `item_type` 造副本子类） | 集中类型分派，避免在应用服务里写 `if/elif` 创建分支 |
| **DTO** | `presentation/schemas/*` | 隔离 ORM 模型与 API 契约；禁止直传 ORM 模型（宪法第六条） |
| **Mapper** | `infrastructure/mappers/*` | ORM 模型 ↔ 领域实体双向转换，保证领域层零框架依赖（R-3） |
| **Unit of Work** | `application/unit_of_work.py` | 显式事务边界，与宪法第九条一致 |

**Strategy 的对照说明**（`07-architecture.md` §4.1 已有正误代码对照）：

```python
# ❌ 被禁止的形态：规则硬编码
def get_max_borrow_count(reader_type: str) -> int:
    if reader_type == "UNDERGRADUATE":
        return 5
    elif reader_type == "GRADUATE":
        return 10
    ...

# ✅ 采用的形态：查表（规则存库，可在线维护）
class BorrowPolicy:
    def limit_for(self, reader_type: ReaderType) -> int:
        return self._table[reader_type].max_borrow_count
```

---

## 13. 人工审查重点自查

对照实验二步骤 1 的 6 项人工审查重点：

| # | 审查重点 | 自查结果 |
|:---:|---|---|
| 1 | Controller 是否只负责接收请求和返回响应？ | ✅ §2.3、§3.3、§6.3 逐类说明「不负责」列，路由函数不含业务判定 |
| 2 | 借书流程是否在 Application Service 中组织？ | ✅ §2.1：`CirculationService.borrow_book` 负责编排，事务边界在此 |
| 3 | 借阅数量和期限检查是否在 `BorrowPolicy` 或服务中？ | ✅ §2.2 步骤 6 由 `BorrowEligibilityService.check_quota` 判定，数值取自 `BorrowPolicy.limit_for` / `days_for` |
| 4 | 罚款计算是否在 `FineRule` 或 `FineService` 中？ | ✅ §8.2：计算内聚在 `FineRule`；本项目不单设 `FineService`，理由见 §1.3 |
| 5 | Repository 是否只负责持久化？ | ✅ §2.3、§5.3：Repository 只做取/存，不含业务判定；`LoanRepository.find_active_by_item` 为查询语义而非规则语义 |
| 6 | 是否为关键异常定义了错误类型？ | ✅ §10：6 个异常类 + 错误码示例 + HTTP 映射，与 `07-architecture.md` §6.2 一致 |

---

## 14. 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|---|---|---|---|
| v1.0 | 2026-09-20 | 初版制定。以用例为单元的详细设计：8 个用例（UC-101/102/102a/005/004/103/201/208/210）逐项给出 Controller 入口、Application Service、Domain Service、Entity/Aggregate、Repository、DTO、异常、事务边界；含 24 个 DTO、6 类异常映射、10 项事务边界、8 处设计模式落点与命名对照表。 | Agent 起草 |
| v1.1 | 2026-09-20 | ① §2.1/§2.2 借书校验的异常与状态码按 `02` FR-016 校准（业务规则失败 400，`CARD_INVALID`/`ITEM_NOT_AVAILABLE`，非 404/409）；② §4.3 预约状态机更正为 4 态（`ACTIVE`/`READY`/`EXPIRED`/`CANCELLED`，删去不存在的 `COMPLETED`）；③ §10 异常表补注「状态码以 `02` FR 为权威来源」。 | Agent 编 API 时交叉核对发现并修订 |
