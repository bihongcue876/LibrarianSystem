# API 接口规范（API Specification）

> **文档编号**：`specs/14-api-spec.md`
> **制定依据**：`02-requirements.md`、`03-use-cases.md`、`09-design-model.md`、`13-database-design.md`
> **版本**：v1.0
> **日期**：2026-09-20
>
> **实现形态**：Web 系统，采用 **REST API**（`07-architecture.md` ADR-01 技术栈：Python + FastAPI）。
>
> **范围说明**：实验二的步骤清单中不含前端实现环节，验收标准为「借书、还书、预约、查询至少可用」+ 自动化测试通过。因此本规范以 **REST 接口**作为系统可用性的交付载体，前端不纳入实验二范围。

---

## 1. 通用约定

### 1.1 基础约定

| 项 | 约定 |
|---|---|
| 基础路径 | `/api` |
| 数据格式 | 请求与响应均为 `application/json`（字符集 UTF-8） |
| 认证方式 | `Authorization: Bearer <JWT>`，Token 有效期 24 小时，无 refresh token（BR-046） |
| 时间格式 | 传输 `ISO 8601`（UTC），前端按北京时间展示（`07-architecture.md` §6.5） |
| 金额格式 | 字符串形式的定点小数，保留 2 位（如 `"9.50"`），避免浮点误差（Q-04） |
| 分页 | 查询类接口支持 `page`（默认 1）与 `page_size`（默认 20，上限 100） |

### 1.2 角色与权限

| 角色代码 | 说明 | 权限范围 |
|---|---|---|
| `READER` | 读者 | 本人数据的查询与自助操作（预约、取消预约、续借、查借阅信息） |
| `LIBRARIAN` | 图书管理员 | 借书、还书、收缴罚款、查询任意读者借阅信息 |
| `SYSTEM_ADMIN` | 系统管理员 | 全部权限，含借阅证管理、账号管理、书目馆藏管理、规则维护、查看已删记录 |

**权限判定原则**：权限校验**必须在服务端完成**，不得依赖前端隐藏按钮（BR-042）。响应 403 时错误码统一为 `PERMISSION_DENIED`。

### 1.3 统一错误响应

```json
{
  "error": {
    "code": "BORROW_LIMIT_EXCEEDED",
    "message": "超出借阅数量上限",
    "detail": { "current": 5, "limit": 5 }
  }
}
```

> **错误码与状态码的权威来源**：**以 `02-requirements.md` 各 FR 的验收标准为准**。`07-architecture.md` §6.2 给出的异常→HTTP 映射是**层级的通用约定**（如 `BusinessRuleError → 409`），当它与具体 FR 的验收标准冲突时，**以 FR 为准**（本文件已逐条按 FR 校准）。因此部分业务规则失败返回 **400** 而非 409——这是 `02` 明确规定的接口行为，不是笔误。

| HTTP | 错误类 | 典型错误码 |
|:---:|---|---|
| 400 | `ValidationError` / `BusinessRuleError` | `CARD_INVALID`、`BORROW_LIMIT_EXCEEDED`、`OVERDUE_LOAN_EXISTS`、`UNPAID_FINE_EXISTS`、`ITEM_NOT_AVAILABLE`、`ITEM_AVAILABLE_NO_RESERVATION`、`CARD_REQUIRED`、`RENEW_LIMIT_EXCEEDED`、`RENEW_OVERDUE`、`INVALID_ISBN` |
| 401 | `UnauthorizedError` | `UNAUTHORIZED`（统一提示"用户名或密码错误"，不区分原因，BR-047） |
| 403 | `ForbiddenError` | `PERMISSION_DENIED` |
| 404 | `NotFoundError` | `ITEM_NOT_FOUND`、`LOAN_NOT_FOUND`、`READER_NOT_FOUND`、`TITLE_NOT_FOUND`、`ACCOUNT_NOT_FOUND` |
| 409 | `ConflictError` | `CARD_ALREADY_EXISTS`、`USERNAME_EXISTS`、`DUPLICATE_RESERVATION`、`RESERVATION_QUEUE_FULL`、`ISBN_EXISTS`、条码重复 |
| 422 | FastAPI 请求体校验 | 字段缺失、类型错误、枚举超范围 |

### 1.4 接口总览

| # | 方法 | 路径 | 权限 | 对应用例 |
|:---:|---|---|---|---|
| 1 | POST | `/api/auth/register` | 公开 | UC-001 注册账号 |
| 2 | POST | `/api/auth/login` | 公开 | UC-002 登录 |
| 3 | POST | `/api/admin/librarians` | `SYSTEM_ADMIN` | UC-206 添加图书管理员 |
| 4 | DELETE | `/api/admin/librarians/{librarian_id}` | `SYSTEM_ADMIN` | UC-207 删除图书管理员 |
| 5 | POST | `/api/admin/accounts/{account_id}/reset-password` | `SYSTEM_ADMIN` | FR-003 验收 5（Q-05） |
| 6 | POST | `/api/admin/borrow-cards` | `SYSTEM_ADMIN` | UC-201 办理借阅证 |
| 7 | POST | `/api/admin/borrow-cards/{card_id}/cancel` | `SYSTEM_ADMIN` | UC-202 注销借阅证 |
| 8 | POST | `/api/admin/borrow-cards/{card_id}/restore` | `SYSTEM_ADMIN` | UC-203 恢复借阅证 |
| 9 | POST | `/api/admin/borrow-cards/{card_id}/suspend` | `SYSTEM_ADMIN` | UC-204 挂失借阅证 |
| 10 | POST | `/api/admin/borrow-cards/{card_id}/resume` | `SYSTEM_ADMIN` | UC-204 解挂借阅证 |
| 11 | GET | `/api/borrow-cards/{card_no}` | 登录用户 | UC-205 查询借阅证信息 |
| 12 | GET | `/api/books` | 公开 | UC-003 查询图书 |
| 13 | POST | `/api/admin/book-titles` | `SYSTEM_ADMIN` | UC-208 添加图书标题 |
| 14 | DELETE | `/api/admin/book-titles/{title_id}` | `SYSTEM_ADMIN` | UC-209 删除图书标题 |
| 15 | POST | `/api/admin/library-items` | `SYSTEM_ADMIN` | UC-210 添加馆藏副本 |
| 16 | DELETE | `/api/admin/library-items/{item_id}` | `SYSTEM_ADMIN` | UC-211 删除馆藏副本 |
| 17 | POST | `/api/admin/library-items/{item_id}/status` | `SYSTEM_ADMIN` | UC-212 标记丢失/破损 |
| 18 | POST | `/api/circulation/precheck` | `LIBRARIAN` | FR-015 借书前置校验 |
| 19 | POST | `/api/circulation/borrow` | `LIBRARIAN` | UC-101 办理借书 |
| 20 | POST | `/api/circulation/return` | `LIBRARIAN` | UC-102 办理还书 |
| 21 | POST | `/api/circulation/loans/{loan_id}/renew` | 读者本人 / `LIBRARIAN` | UC-007 续借图书 |
| 22 | GET | `/api/me/loans` | `READER` | UC-004 查询借阅信息 |
| 23 | GET | `/api/readers/{reader_id}/loans` | `LIBRARIAN`、`SYSTEM_ADMIN` | UC-103 查询读者借阅信息 |
| 24 | POST | `/api/fines/{fine_id}/collect` | `LIBRARIAN` | UC-104 收缴罚款 |
| 25 | GET | `/api/me/fines` | `READER` | FR-026 罚款查询 |
| 26 | POST | `/api/reservations` | `READER` | UC-005 预约图书 |
| 27 | DELETE | `/api/reservations/{reservation_id}` | 读者本人 | UC-006 取消预约 |
| 28 | GET | `/api/me/reservations` | `READER` | FR-024 查询预约状态 |
| 29 | GET | `/api/policies` | 登录用户 | UC-213/214 规则查询 |
| 30 | PUT | `/api/admin/policies/borrow` | `SYSTEM_ADMIN` | UC-213 维护借阅规则 |
| 31 | PUT | `/api/admin/policies/fine` | `SYSTEM_ADMIN` | UC-214 维护罚款规则 |
| 32 | GET | `/api/admin/collection-stats` | `SYSTEM_ADMIN` | UC-215 查询馆藏统计 |

---

## 2. 认证与账号接口

### 2.1 注册读者

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/auth/register` |
| **权限要求** | 公开（无需 Token） |
| **对应需求** | FR-002、BR-048 |

**请求参数**：

| 字段 | 类型 | 必填 | 约束 |
|---|---|:---:|---|
| `username` | string | ✅ | 3-32 位，仅字母/数字/下划线；**全局唯一，软删除不释放**（Q-03） |
| `password` | string | ✅ | 6-24 位，无复杂度要求（BR-045） |
| `name` | string | ✅ | 非空 |
| `department` | string | ✅ | 院系 |
| `reader_type` | string | ✅ | `COLLEGE` / `UNDERGRADUATE` / `GRADUATE` / `DOCTOR` / `TEACHER` |

**成功响应**（201）：返回账号 ID、用户名、角色（`READER`）。

**失败场景**：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 用户名已存在 | 409 | `USERNAME_EXISTS` |
| 密码长度不足或超长 | 422 | 参数校验错误 |
| `reader_type` 不在枚举内 | 422 | 参数校验错误 |
| 用户名含非法字符 | 422 | 参数校验错误 |

> **注意**：注册成功后**不具备借阅资格**，须由系统管理员办理借阅证（BR-012）。

### 2.2 登录

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/auth/login` |
| **权限要求** | 公开 |
| **对应需求** | FR-001、BR-046、BR-047 |

**请求参数**：`username`、`password`（均必填）。

**成功响应**（200）：`access_token`、`token_type`（`bearer`）、`role`、`account_id`、`expires_at`。

**失败场景**：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 用户名不存在或密码错误 | 401 | `UNAUTHORIZED`，提示统一为"用户名或密码错误"，**不区分具体原因**（BR-047） |
| 账号已软删除 | 401 | `UNAUTHORIZED` |

### 2.3 添加图书管理员

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/admin/librarians` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-003 |

**请求参数**：`username`、`password`、`name`（均必填）。

**成功响应**（201）：账号 ID、用户名、角色 `LIBRARIAN`。

**失败场景**：非系统管理员 → 403 `PERMISSION_DENIED`；用户名重复 → 409 `USERNAME_EXISTS`。

### 2.4 删除图书管理员

| 项 | 内容 |
|---|---|
| **方法与路径** | `DELETE /api/admin/librarians/{librarian_id}` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-003、FR-004、BR-043 |

**成功响应**（200）：软删除成功，账号不可再登录；历史借阅记录中的 `librarian_id` 仍可追溯。

**失败场景**：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 目标不存在 | 404 | `ACCOUNT_NOT_FOUND` |
| 目标角色为 `SYSTEM_ADMIN` | 403 | `PERMISSION_DENIED`（系统管理员之间不可互相删除，BR-043） |
| 非系统管理员调用 | 403 | `PERMISSION_DENIED` |

### 2.5 重置密码

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/admin/accounts/{account_id}/reset-password` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-003 验收标准 5（Q-05 裁定落点） |

**请求参数**：`new_password`（必填，6-24 位）。

**成功响应**（200）：重置成功。

**说明**：系统**不提供自助找回密码**接口。前端「忘记密码」仅提示"请联系管理员重置密码"。

**失败场景**：目标账号不存在 → 404；非系统管理员 → 403。

---

## 3. 借阅证管理接口

### 3.1 办理借阅证

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/admin/borrow-cards` |
| **权限要求** | `SYSTEM_ADMIN`（BR-041） |
| **对应需求** | FR-005、UC-201、BR-003 |

**请求参数**：`reader_id`（必填）。

**成功响应**（201）：

```json
{
  "card_id": 1,
  "card_no": "CARD2026000001",
  "reader_id": 10,
  "status": "ACTIVE",
  "issued_at": "2026-09-20T02:30:00Z",
  "issued_by": 1
}
```

**失败场景**：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 读者不存在或已软删除 | 404 | `READER_NOT_FOUND` |
| 该读者已有有效借阅证 | 409 | `CARD_ALREADY_EXISTS`（BR-003；`CANCELLED` 不计入） |
| 非系统管理员 | 403 | `PERMISSION_DENIED` |

### 3.2 注销 / 恢复 / 挂失 / 解挂借阅证

| 接口 | 方法与路径 | 请求参数 | 成功响应 | 关键失败场景 |
|---|---|---|---|---|
| 注销 | `POST /api/admin/borrow-cards/{card_id}/cancel` | `reason`（可空） | 200，`status` → `CANCELLED` | 证不存在 404；证非 `ACTIVE`/`SUSPENDED` 400 |
| 恢复 | `POST /api/admin/borrow-cards/{card_id}/restore` | 无 | 200，`status` → `ACTIVE` | 证不存在 404；证非 `CANCELLED` 400；该读者已有其他有效证 409 `CARD_ALREADY_EXISTS`（FR-007 验收 2） |
| 挂失 | `POST /api/admin/borrow-cards/{card_id}/suspend` | 无 | 200，`status` → `SUSPENDED` | 证不存在 404；证非 `ACTIVE` 400 |
| 解挂 | `POST /api/admin/borrow-cards/{card_id}/resume` | 无 | 200，`status` → `ACTIVE` | 证不存在 404；证非 `SUSPENDED` 400 |

**权限**：以上四个接口均限 `SYSTEM_ADMIN`。

> **状态机约束**：`ACTIVE` ⇄ `SUSPENDED`，`ACTIVE`/`SUSPENDED` → `CANCELLED` → `ACTIVE`（恢复）。状态流转只能通过上述接口，**不允许外部直接改 `status` 字段**（`06-domain-class-diagram.md` §3）。

### 3.3 查询借阅证信息

| 项 | 内容 |
|---|---|
| **方法与路径** | `GET /api/borrow-cards/{card_no}` |
| **权限要求** | 登录用户（读者仅可查本人证） |
| **对应需求** | FR-009、UC-205 |

**成功响应**（200）：证号、状态、持证人、签发时间、签发人。

**失败场景**：证不存在 → 404；读者查询他人证 → 403 `PERMISSION_DENIED`。

---

## 4. 书目与馆藏接口

### 4.1 查询图书

| 项 | 内容 |
|---|---|
| **方法与路径** | `GET /api/books` |
| **权限要求** | 公开（无需登录） |
| **对应需求** | FR-014、UC-003 |

**请求参数（查询串）**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| `keyword` | string | ⬜ | 按题名 / 作者 / ISBN 模糊匹配 |
| `item_type` | string | ⬜ | 借出物类型筛选 |
| `available_only` | bool | ⬜ | 仅返回有可借副本的题录，默认 `false` |
| `page` / `page_size` | int | ⬜ | 分页 |

**成功响应**（200）：题录列表，每条含 `title_id`、`title`、`author`、`isbn`、`publisher`、`item_type`、`total_items`、`available_items`（可借副本数）。

**失败场景**：参数类型错误 → 422。

> **过滤规则**：已软删除的题录与副本**不出现在结果中**（BR-037）。

### 4.2 添加图书标题

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/admin/book-titles` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-010、UC-208 |

**请求参数**：

| 字段 | 类型 | 必填 | 约束 |
|---|---|:---:|---|
| `title` | string | ✅ | 题名 |
| `author` | string | ✅ | 作者 |
| `isbn` | string | ⬜ | 格式校验（`Isbn.is_valid`）；**部分唯一索引：仅活跃记录查重**，便于已下架书的重新采购（`13` §4.1） |
| `publisher` | string | ⬜ | 出版社 |
| `publish_year` | int | ⬜ | 出版年 |
| `item_type` | string | ✅ | `CHINESE_BOOK` / `FOREIGN_BOOK` / `CHINESE_MAGAZINE` / `FOREIGN_MAGAZINE` / `THESIS` |
| `language` | string | ⬜ | 语种 |

**成功响应**（201）：`title_id` 与题录信息。

**失败场景**：非系统管理员 403；ISBN 格式非法 400 `INVALID_ISBN`；ISBN 与活跃记录重复 409 `ISBN_EXISTS`；`item_type` 非法 422。

> **允许在无任何副本的状态下创建题录**（BR-014）。

### 4.3 删除图书标题

| 项 | 内容 |
|---|---|
| **方法与路径** | `DELETE /api/admin/book-titles/{title_id}` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-011 |

**成功响应**（200）：题录软删除，其下副本**同步置 `REMOVED`**（FR-011 验收标准 3）。

**行为说明（易实现错，需注意）**：若该题录下存在未归还的借阅记录，**删除不失败**——该副本保持 `BORROWED` 直至归还，归还后置为 `REMOVED`（FR-011 验收标准 4）。

**失败场景**：题录不存在 404 `TITLE_NOT_FOUND`；非系统管理员 403 `PERMISSION_DENIED`。

### 4.4 添加馆藏副本

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/admin/library-items` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-012、UC-210 |

**请求参数**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| `title_id` | int | ✅ | 所属题录 |
| `location` | string | ⬜ | 馆藏位置 |
| `price` | string | ⬜ | 定价，定点小数 |
| `acquired_at` | string | ⬜ | 入藏日期 |

**成功响应**（201）：`item_id`、`barcode`（格式 `BC` + 8 位序号，如 `BC00000001`）、`status` = `AVAILABLE`。

**失败场景**：题录不存在 404；条码重复 409；非系统管理员 403。

> **实现说明**：副本类型由题录的 `item_type` 决定，经 `LibraryItemFactory` 分派到 `Book` / `Magazine` / `Thesis`；持久化采用**单表继承**（`library_items` 表 + `item_type` 判别列）。

### 4.5 删除馆藏副本 / 标记丢失破损

| 接口 | 方法与路径 | 请求参数 | 成功响应 | 关键失败场景 |
|---|---|---|---|---|
| 删除副本 | `DELETE /api/admin/library-items/{item_id}` | 无 | 200，`status` → `REMOVED` | 副本不存在 404；状态为 `BORROWED` → **400**（不允许直接删除，FR-013 验收 4） |
| 标记丢失/破损 | `POST /api/admin/library-items/{item_id}/status` | `status`（`LOST` / `DAMAGED` / `AVAILABLE`） | 200 | 副本不存在 404；非法状态值 422；副本在借 400 |

**权限**：均为 `SYSTEM_ADMIN`。**对应需求**：FR-013、UC-211、UC-212。

> **副本状态语义**：`REMOVED`、`LOST`、`DAMAGED` 三种状态的副本均不可借出——借书时返回 `ITEM_NOT_AVAILABLE`（FR-013 验收 3）。

---

## 5. 流通接口

### 5.1 借书前置校验（预检查）

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/circulation/precheck` |
| **权限要求** | `LIBRARIAN`、`SYSTEM_ADMIN` |
| **对应需求** | FR-015（借书两阶段流程的前置确认） |

**请求参数**：`card_no`。

**成功响应**（200）：读者信息 + 额度信息 + 三项告警标志，**不产生任何副作用**。

```json
{
  "reader": { "reader_id": 10, "name": "张三", "reader_type": "UNDERGRADUATE" },
  "quota": { "limit": 5, "occupied": 2, "remaining": 3 },
  "alerts": { "has_overdue": false, "has_unpaid_fine": false, "has_due_soon": true },
  "can_borrow": true
}
```

**失败场景**：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 借阅证无效（不存在或状态非 `ACTIVE`） | 400 | `CARD_INVALID`（FR-015 验收 3） |
| 非图书管理员/系统管理员调用 | 403 | `PERMISSION_DENIED` |

**说明**：本接口为**只读**（FR-015 验收 5）。与 UC-101 的六项校验顺序一致；最终以 `POST /api/circulation/borrow` 的校验结果为准。

### 5.2 办理借书

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/circulation/borrow` |
| **权限要求** | `LIBRARIAN`、`SYSTEM_ADMIN` |
| **对应需求** | FR-016、UC-101 |

**请求参数**：`card_no`（借阅证号）、`barcode`（馆藏条码）。

**成功响应**（201）：

```json
{
  "loan_id": 100,
  "reader_id": 10,
  "item_id": 5,
  "barcode": "BC00000001",
  "borrowed_at": "2026-09-20T02:30:00Z",
  "due_at": "2026-10-20T02:30:00Z",
  "status": "BORROWED",
  "remaining_quota": 4
}
```

**失败场景**（按固定校验顺序，**遇首个失败即返回**；错误码与状态码依 FR-016 验收标准 2）：

| 顺序 | 场景 | HTTP | 错误码 |
|:---:|---|:---:|---|
| 1 | 操作人非图书管理员/系统管理员 | 403 | `PERMISSION_DENIED` |
| 2 | 借阅证不存在或状态非 `ACTIVE` | 400 | `CARD_INVALID` |
| 3 | 未超出最大借阅数量（已占额度 ≥ 上限） | 400 | `BORROW_LIMIT_EXCEEDED` |
| 4 | 不存在超期未还的借阅记录 | 400 | `OVERDUE_LOAN_EXISTS` |
| 5 | 不存在未缴清的罚款 | 400 | `UNPAID_FINE_EXISTS` |
| 6 | 馆藏副本存在、属本馆、状态为 `AVAILABLE` | 400 | `ITEM_NOT_AVAILABLE` |

> **注意状态码**：以上业务规则失败在 `02` FR-016 中被规定为 **400**（而非 409），实现时以此为准。`detail` 字段可携带上下文（如 `{"current": 5, "limit": 5}`）。

> **事务要求**：整个操作在**单个事务**内完成，任一失败**全部回滚**（FR-016 验收 3）——副本状态不得残留变更。

### 5.3 办理还书

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/circulation/return` |
| **权限要求** | `LIBRARIAN`、`SYSTEM_ADMIN` |
| **对应需求** | FR-017、UC-102、UC-102a |

**请求参数**：`barcode`（**仅凭馆藏条码，不要求借阅证**）。

**成功响应**（200）：

```json
{
  "loan_id": 100,
  "returned_at": "2026-09-20T02:30:00Z",
  "overdue_days": 3,
  "fine": { "fine_id": 7, "amount": "0.50", "status": "UNPAID" },
  "item_status": "RESERVED",
  "reservation_advanced": { "reservation_id": 12, "status": "READY" }
}
```

**失败场景**：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 非馆员/管理员角色 | 403 | `PERMISSION_DENIED` |
| 条码不存在（非本馆藏书） | 404 | `ITEM_NOT_FOUND` |
| 未找到该副本的在借记录 | 404 | `LOAN_NOT_FOUND` |

**行为说明**：

1. 超期则生成 `FineRecord`（`overdue_days ≤ 宽限天数` 时不生成）。
2. 副本去向：该题录有有效预约队列 → 队首置 `READY`、副本置 `RESERVED`（BR-024a）；否则置 `AVAILABLE`。
3. 队列失效判定为**惰性**，但须在**同一次操作内**完成顺延与交接（BR-025b）。

### 5.4 续借图书

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/circulation/loans/{loan_id}/renew` |
| **权限要求** | 借阅人本人（读者自助）或 `LIBRARIAN` |
| **对应需求** | FR-018、UC-007、BR-015 ~ BR-019 |

**成功响应**（200）：新的 `due_at`、`renew_count`（+1）。

**失败场景**（依 FR-018 验收标准 2/3/5）：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 借阅记录不存在 | 404 | `LOAN_NOT_FOUND` |
| 尝试续借他人名下的记录 | 403 | `PERMISSION_DENIED`（FR-018 验收 5） |
| 已续借 2 次 | 400 | `RENEW_LIMIT_EXCEEDED`（FR-018 验收 2） |
| 已超期 | 400 | `RENEW_OVERDUE`（FR-018 验收 3） |
| 当前占用额度已超出上限 | 400 | `BORROW_LIMIT_EXCEEDED`（FR-018 验收 4） |

**规则说明**：续借每次 +7 天（BR-015）；**存在预约排队不影响续借资格**（BR-018 / FR-018 验收 7）；续借不额外占用额度（BR-019）。

### 5.5 查询借阅信息（读者本人）

| 项 | 内容 |
|---|---|
| **方法与路径** | `GET /api/me/loans` |
| **权限要求** | `READER`（读者本人） |
| **对应需求** | FR-019、UC-004 |

**请求参数**：`status`（`current` / `history` / `overdue`，可空表示全部）、分页参数。

**成功响应**（200）：**四段结构**（依 FR-019 验收标准 1~4）——`current`（当前借阅：书名、条码、借出时间、到期时间、剩余天数、是否超期、是否可续借、已续借次数）、`history`（历史借阅）、`reservations`（预约列表：标题、状态、排队位置）、`fines`（罚款记录：金额、缴纳状态、产生时间）。

**响应字段裁剪（安全要求）**：读者视角的响应中**不返回经办图书管理员 ID**（`librarian_id` 为内部审计字段，FR-019 验收 6）。

**失败场景**：未登录 401。**读者只能查看本人数据**，服务端不信任任何请求参数中的 `reader_id`（BR-039）。

### 5.6 查询读者借阅信息（馆员代理）

| 项 | 内容 |
|---|---|
| **方法与路径** | `GET /api/readers/{reader_id}/loans` |
| **权限要求** | `LIBRARIAN`、`SYSTEM_ADMIN` |
| **对应需求** | FR-019、UC-103 |

**成功响应**（200）：同上三段结构，额外附该读者的未缴罚款汇总。

**失败场景**：读者不存在 404；读者角色无权调用此接口 403 `PERMISSION_DENIED`。

### 5.7 收缴罚款

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/fines/{fine_id}/collect` |
| **权限要求** | `LIBRARIAN`、`SYSTEM_ADMIN`（BR-031、BR-040） |
| **对应需求** | FR-026、UC-104 |

**成功响应**（200）：`fine_id`、`status` = `PAID`、`paid_at`、`operator_id`、`operator_role`。

**失败场景**：罚款记录不存在 404；已收缴（重复收缴）400 `FINE_ALREADY_PAID`；非馆员/管理员 403。

**说明**：系统**不接入在线支付**，罚款为线下收取后在系统中标记（BR-031）。

### 5.8 查询本人罚款

| 项 | 内容 |
|---|---|
| **方法与路径** | `GET /api/me/fines` |
| **权限要求** | `READER` |
| **对应需求** | FR-026 |

**成功响应**（200）：`unpaid` 与 `paid` 两组，含金额、超期天数、计罚天数、状态。

---

## 6. 预约接口

### 6.1 预约图书

| 项 | 内容 |
|---|---|
| **方法与路径** | `POST /api/reservations` |
| **权限要求** | `READER` |
| **对应需求** | FR-021、UC-005 |

**请求参数**：`title_id`（必填）。

> **安全约束**：预约人取自 JWT 中的账号身份，**不接受请求体中的 `reader_id`**（BR-039）。

**成功响应**（201）：

```json
{
  "reservation_id": 12,
  "title_id": 3,
  "status": "ACTIVE",
  "created_at": "2026-09-20T02:30:00Z",
  "queue_position": 2,
  "expires_at": "2026-09-27T02:30:00Z"
}
```

**失败场景**（依 FR-021 验收标准 2~6）：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 未登录 | 401 | `UNAUTHORIZED` |
| 读者不存在或已软删除 | 404 | `READER_NOT_FOUND` |
| 标题不存在或已软删除 | 404 | `TITLE_NOT_FOUND` |
| 该标题下存在任一 `AVAILABLE` 副本 | 400 | `ITEM_AVAILABLE_NO_RESERVATION`（FR-021 验收 2） |
| 读者无有效借阅证 | 400 | `CARD_REQUIRED`（FR-021 验收 5） |
| 已有该标题的有效预约（`ACTIVE`/`READY`） | 409 | `DUPLICATE_RESERVATION`（FR-021 验收 3） |
| 预约队列已达 5 人 | 409 | `RESERVATION_QUEUE_FULL`（FR-021 验收 4） |

### 6.2 取消预约

| 项 | 内容 |
|---|---|
| **方法与路径** | `DELETE /api/reservations/{reservation_id}` |
| **权限要求** | 预约人本人 |
| **对应需求** | FR-022、UC-006、BR-025a |

**成功响应**（200）：`status` → `CANCELLED`；若该预约持有 `RESERVED` 副本，副本**转交下一位预约者**并保持 `RESERVED`（BR-024a）；队列无有效预约时才释放为 `AVAILABLE`。

**失败场景**（依 FR-022 验收标准 3/4）：

| 场景 | HTTP | 错误码 |
|---|:---:|---|
| 预约不存在 | 404 | `RESERVATION_NOT_FOUND` |
| 取消他人预约 | 403 | `PERMISSION_DENIED` |
| 取消失效（`EXPIRED`）或已取消（`CANCELLED`）的预约 | 400 | `RESERVATION_NOT_CANCELLABLE` |

**说明**：`ACTIVE` 与 `READY` 两种状态**均可取消**（BR-025a）。

### 6.3 查询预约状态

| 项 | 内容 |
|---|---|
| **方法与路径** | `GET /api/me/reservations` |
| **权限要求** | `READER` |
| **对应需求** | FR-024、UC-004 步骤 5 |

**成功响应**（200）：当前有效预约列表，每条含题名、状态、排队位置、到书时间（`READY` 时）、有效期。

**失败场景**：未登录 401。

---

## 7. 规则维护接口

### 7.1 查询规则

| 项 | 内容 |
|---|---|
| **方法与路径** | `GET /api/policies` |
| **权限要求** | 登录用户（读者需知晓本人额度与期限） |
| **对应需求** | FR-027、FR-028 |

**成功响应**（200）：`borrow_policies`（5 种读者类型）与 `fine_rules`（5 种借出物类型）两组当前值。

### 7.2 维护借阅规则

| 项 | 内容 |
|---|---|
| **方法与路径** | `PUT /api/admin/policies/borrow` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-027、UC-213、BR-049 |

**请求参数**：`reader_type`、`max_borrow_count`（≥1）、`borrow_days`（≥1）。

**成功响应**（200）：更新后的规则值，含 `updated_at`、`updated_by`。

**失败场景**：非系统管理员 403；`reader_type` 非法 422；数值非法（≤0）422。

> **行为说明**：规则修改**只影响之后创建的借阅**，已存在的 `Loan.due_at` 不受影响（BR-050：借期在创建时快照）。

### 7.3 维护罚款规则

| 项 | 内容 |
|---|---|
| **方法与路径** | `PUT /api/admin/policies/fine` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-028、UC-214 |

**请求参数**：`item_type`、`daily_price`（定点小数字符串，≥0）、`grace_days`（≥0）、`max_amount`（≥0）。

**成功响应**（200）：更新后的规则值。

**失败场景**：同 7.2。

**规则语义**：

```
计罚天数 = max(超期天数 − 宽限天数, 0)
罚款金额 = min(计罚天数 × 日单价, 封顶金额)
```

> **行为说明**：`FineRecord` 在创建时**快照 `unit_price`**，规则修改不追溯已生成的罚款（BR-050）。

---

## 8. 统计接口

### 8.1 查询馆藏统计

| 项 | 内容 |
|---|---|
| **方法与路径** | `GET /api/admin/collection-stats` |
| **权限要求** | `SYSTEM_ADMIN` |
| **对应需求** | FR-029、UC-215 |

**成功响应**（200）：题录总数、副本总数、按状态分组的副本数（`AVAILABLE`/`BORROWED`/`RESERVED`/`LOST`/`DAMAGED`/`REMOVED`）、按 `item_type` 分组的副本数。

**失败场景**：非系统管理员 403。

---

## 9. 与实验文档要求的对照

| 实验文档要求覆盖的接口 | 本规范条目 | 判定 |
|---|---|---|
| 注册读者 | §2.1 | ✅ |
| 办理借阅证 | §3.1 | ✅ |
| 查询图书 | §4.1 | ✅ |
| 办理借书 | §5.2 | ✅ |
| 办理还书 | §5.3 | ✅ |
| 查询借阅信息 | §5.5、§5.6 | ✅ |
| 预约图书 | §6.1 | ✅ |
| 添加图书标题 | §4.2 | ✅ |
| 添加馆藏副本 | §4.4 | ✅ |
| 维护规则 | §7.2、§7.3 | ✅ |

**每接口均含**：方法与路径、请求参数、响应结果、权限要求、成功场景、失败场景（含 HTTP 状态码与错误码）。

---

## 10. 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|---|---|---|---|
| v1.0 | 2026-09-20 | 初版制定。32 个 REST 接口，含通用约定、权限矩阵、统一错误响应、10 类实验文档点名接口的完整定义与失败场景。 | Agent 起草 |
| v1.1 | 2026-09-20 | **逐条对照 `02-requirements.md` 的 FR 验收标准校准错误码与状态码**（编写时误按 `07` §6.2 的层级映射写成 409）。修正 11 处：① 借书校验失败状态码 409 → **400**，错误码改为 `CARD_INVALID`/`OVERDUE_LOAN_EXISTS`/`ITEM_NOT_AVAILABLE`；② 预检查响应改为读者信息 + 额度 + 三项告警（依 FR-015）；③ 续借错误码改为 `RENEW_LIMIT_EXCEEDED`/`RENEW_OVERDUE`（400）；④ 预约错误码改为 `ITEM_AVAILABLE_NO_RESERVATION`（400）、补 `CARD_REQUIRED`；⑤ 取消预约按 FR-022 补全；⑥ §4.3 删去"有未归还副本则 409"（FR-011 验收 4 明确删除**不失败**）；⑦ §4.5 副本删除 `BORROWED` 状态 409 → **400**（FR-013 验收 4）；⑧ §3.2 注销删去虚构的"有未归还借阅则 409"；⑨ §5.5 查询借阅信息改为四段结构并补"不返回经办管理员 ID"；⑩ §1.3 明确错误码以 `02` FR 为权威来源；⑪ §4.3 规则引用 `BR-042`（实为权限规则）更正为 `FR-011`。 | Agent 编 API 时交叉核对发现并修订 |
