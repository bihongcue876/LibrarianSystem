# 领域模型（Domain Model）

> **文档编号**：`specs/05-domain-model.md`
> **制定依据**：`02-requirements.md`、`03-use-cases.md`、`01-clarifying-questions.md`
> **版本**：v1.0
> **日期**：2026-09-19
>
> 本文件定义系统的领域模型。领域模型是**业务概念的抽象**，而非数据库表的机械翻译。
> 本文件**不包含**任何设计类（Controller、Repository、DTO）——那些属于 `09-design-model.md` 的范畴。
>
> 领域模型使用的核心概念：
> - **实体 Entity** — 有唯一标识，生命周期内标识不变
> - **值对象 Value Object** — 无唯一标识，由属性值定义相等性，不可变
> - **领域服务 Domain Service** — 承载跨实体的业务规则，本身无状态
> - **策略对象 Policy** — 可替换的业务规则集合（Strategy 模式的领域侧体现）
> - **枚举 Enumeration** — 固定的取值集合

---

## 1. 领域模型总览

### 1.1 限界上下文（Bounded Context）

本系统为单一限界上下文「图书馆流通管理」，内部划分为 7 个领域模块：

| 模块 | 中文名 | 核心概念 |
|---|---|---|
| `reader` | 读者模块 | 读者身份、类型、额度 |
| `card` | 借阅证模块 | 借阅证的签发、状态流转 |
| `catalog` | 书目模块 | 图书标题、馆藏副本、可借性 |
| `circulation` | 流通模块 | 借出、归还、续借、超期判定 |
| `reservation` | 预约模块 | 预约队列、到书预留、失效 |
| `fine` | 罚款模块 | 超期罚款的计算与记录 |
| `policy` | 规则模块 | 借阅规则、罚款规则的可配置定义 |

### 1.2 领域对象分类总表

> 下表是本文件的索引，详细定义见后续章节。

| 类别 | 领域对象 | 归属模块 |
|---|---|---|
| **实体** | `Reader`（抽象） | reader |
| **实体** | `StudentReader` / `TeacherReader` | reader |
| **实体** | `BorrowCard` | card |
| **实体** | `BookTitle` | catalog |
| **实体** | `LibraryItem`（抽象） | catalog |
| **实体** | `Book` / `Magazine` / `Thesis` | catalog |
| **实体** | `Loan` | circulation |
| **实体** | `Reservation` | reservation |
| **实体** | `FineRecord` | fine |
| **实体** | `Librarian` / `SystemAdmin` | reader（账号子域） |
| **值对象** | `CardNumber` | card |
| **值对象** | `Barcode` | catalog |
| **值对象** | `Isbn` | catalog |
| **值对象** | `ReaderType`（枚举） | reader |
| **值对象** | `ItemType`（枚举） | catalog |
| **值对象** | `ItemStatus`（枚举） | catalog |
| **值对象** | `CardStatus`（枚举） | card |
| **值对象** | `LoanStatus`（枚举） | circulation |
| **值对象** | `ReservationStatus`（枚举） | reservation |
| **值对象** | `FineStatus`（枚举） | fine |
| **值对象** | `Money` | fine |
| **值对象** | `DateRange` | circulation |
| **领域服务** | `BorrowEligibilityService` | circulation |
| **领域服务** | `RenewalService` | circulation |
| **领域服务** | `ReservationQueueService` | reservation |
| **策略对象** | `BorrowPolicy` | policy |
| **策略对象** | `FineRule` | policy |

**对象总数**：14 个实体、12 个值对象/枚举、3 个领域服务、2 个策略对象。

> **计数口径**：实体数含抽象基类（`Reader`、`LibraryItem`）与其全部具体子类（`StudentReader`、`TeacherReader`、`Book`、`Magazine`、`Thesis`）。

---

## 2. 读者模块（reader）

### 2.1 Reader（读者，抽象实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体（抽象基类） |
| **职责** | 表示具备借阅资格的自然人，承载借阅额度与身份信息 |
| **标识** | `reader_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `reader_id` | 标识 | 唯一标识 |
| `name` | 字符串 | 姓名 |
| `department` | 字符串 | 院系或单位 |
| `reader_type` | ReaderType | 读者类型（区分具体子类） |
| `username` | 字符串 | 登录用户名，全局唯一 |
| `password_hash` | 字符串 | bcrypt 哈希后的密码 |
| `is_deleted` | 布尔 | 软删除标记 |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `borrow_limit(policy)` | 返回本读者的最大借阅数量（委托给 `BorrowPolicy`） |
| `borrow_days(policy)` | 返回本读者的借阅期限天数（委托给 `BorrowPolicy`） |
| `occupies_quota(loans, reservations)` | 计算当前占用的借阅额度 |
| `can_borrow(loans, reservations, fines)` | 判断是否满足借书条件（综合额度、超期、欠款） |

**约束**：

- `username` 全局唯一，长度 3-32 位，仅字母/数字/下划线（BR-048）。
- `password_hash` 必须为 bcrypt 哈希，不得存明文（BR-045）。
- 一个自然人对同一角色最多一个账号；不同角色可各自拥有账号（BR-044）。

**关系**：

- `Reader` ← `StudentReader` / `TeacherReader`（继承）
- `Reader` 1 — 0..1 `BorrowCard`（一个读者最多一张有效借阅证）
- `Reader` 1 — 0..* `Loan`（一个读者有多条借阅记录）
- `Reader` 1 — 0..* `Reservation`（一个读者有多个预约）

**约束说明**：`Reader` 是**抽象类**，不允许直接实例化。实际使用的是其子类。

---

### 2.2 StudentReader（学生读者，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体（`Reader` 的子类） |
| **职责** | 表示学生身份的读者，按学历层次区分借阅额度 |

**特有属性**：`student_type` — 取值 `COLLEGE` / `UNDERGRADUATE` / `GRADUATE` / `DOCTOR`

**关键行为**：

- 覆写 `borrow_limit(policy)`：从 `BorrowPolicy` 查询对应学历的额度。
  - 专科生 5 册、本科生 5 册、研究生 10 册、博士生 15 册
- 覆写 `borrow_days(policy)`：
  - 专科生 30 天、本科生 30 天、研究生 60 天、博士生 90 天

**约束**：`student_type` 必须在允许枚举内。

---

### 2.3 TeacherReader（教师读者，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体（`Reader` 的子类） |
| **职责** | 表示教师身份的读者，借阅额度最高 |

**关键行为**：

- 覆写 `borrow_limit(policy)`：20 册
- 覆写 `borrow_days(policy)`：90 天

**关系**：`TeacherReader` 1 — 0..* `Loan`，`TeacherReader` 1 — 0..* `Reservation`

---

### 2.4 Librarian（图书管理员，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体 |
| **职责** | 代理读者办理借书、还书，查询借阅信息，收缴罚款 |
| **标识** | `librarian_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `librarian_id` | 标识 | 唯一标识 |
| `name` | 字符串 | 姓名 |
| `username` | 字符串 | 登录用户名，全局唯一 |
| `password_hash` | 字符串 | bcrypt 哈希 |
| `is_deleted` | 布尔 | 软删除标记 |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `can_borrow_for(card)` | 判断是否为有效借阅证办理借书 |
| `can_collect_fine(fine_record)` | 判断是否可收缴指定罚款 |

**约束**：

- 图书管理员账号**不可**自助注册，只能由系统管理员创建（BR-041）。
- 图书管理员**不可**管理借阅证、账号、书目、馆藏、规则（BR-041）。
- 软删除后不可登录，但其经办的借阅记录仍可追溯（BR-036）。

**关系**：

- `Librarian` 1 — 0..* `Loan`（作为经办人）
- `Librarian` 1 — 0..* `FineRecord`（作为收缴人）

---

### 2.5 SystemAdmin（系统管理员，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体 |
| **职责** | 维护借阅证、账号、书目、馆藏、借阅规则与罚款规则 |
| **标识** | `admin_id` |

**关键属性**：`admin_id`、`name`、`username`、`password_hash`、`is_deleted`

**关键行为**：

| 方法 | 说明 |
|---|---|
| `issue_card(reader)` | 为读者办理借阅证 |
| `cancel_card(card)` | 注销借阅证 |
| `restore_card(card)` | 恢复已注销的借阅证 |
| `maintain_policy(policy, new_value)` | 维护借阅规则或罚款规则 |

**约束**：

- 系统管理员账号只能通过初始化脚本创建，**不提供在线创建接口**。
- 系统管理员**之间不可互相删除**（BR-043）。
- 系统中至少保留一个可用的系统管理员账号。

**关系**：

- `SystemAdmin` 1 — 0..* `BorrowCard`（作为签发人）
- `SystemAdmin` 1 — 0..* `BookTitle`（作为录入人）
- `SystemAdmin` 1 — 0..* `LibraryItem`（作为录入人）

---

## 3. 借阅证模块（card）

### 3.1 BorrowCard（借阅证，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体（聚合根） |
| **职责** | 表示读者的借阅凭证，控制借阅资格的授予与撤销 |
| **标识** | `card_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `card_id` | 标识 | 唯一标识 |
| `card_no` | CardNumber | 借阅证号（值对象），全局唯一 |
| `reader_id` | 标识 | 所属读者 |
| `status` | CardStatus | 状态 |
| `issued_at` | 时间戳 | 办证时间 |
| `issued_by` | 标识 | 经办系统管理员 |
| `cancelled_at` | 时间戳 | 注销时间（可空） |
| `expired_at` | 时间戳 | 过期时间（可空，当前不使用） |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `issue(reader, admin)` | 签发借阅证，生成证号，状态置为 `ACTIVE` |
| `cancel(admin)` | 注销，状态置为 `CANCELLED` |
| `restore(admin)` | 恢复，状态由 `CANCELLED` 置为 `ACTIVE` |
| `suspend(admin)` | 挂失，状态由 `ACTIVE` 置为 `SUSPENDED` |
| `resume(admin)` | 解挂，状态由 `SUSPENDED` 置为 `ACTIVE` |
| `is_valid()` | 判断状态是否为 `ACTIVE` |

**约束**：

- `card_no` 全局唯一（BR-004）。
- 一名读者最多一张有效证（`ACTIVE` 或 `SUSPENDED`）；`CANCELLED` 不计入（BR-003）。
- 不设过期时间，`expired_at` 字段保留但不校验（BR-005）。
- 注销为软删除，记录永久保留（BR-036）。

**关系**：`BorrowCard` * — 1 `Reader`

**状态机**：

```
                 办证
       [无证] ──────────→ ACTIVE
                            │  ↑
                挂失 ┌──────┘  │ 解挂
                     ↓        │
                SUSPENDED ────┘
                     │
              注销 ┌──┴──┐ 注销
                   ↓     ↓
              CANCELLED ──┐
                   ↑       │ 恢复
                   └───────┘
```

**状态转移合法性**：

| 起始状态 | 目标状态 | 触发操作 | 合法性 |
|---|---|---|---|
| 无 | `ACTIVE` | 办证 | ✅ |
| `ACTIVE` | `SUSPENDED` | 挂失 | ✅ |
| `ACTIVE` | `CANCELLED` | 注销 | ✅ |
| `SUSPENDED` | `ACTIVE` | 解挂 | ✅ |
| `SUSPENDED` | `CANCELLED` | 注销 | ✅ |
| `CANCELLED` | `ACTIVE` | 恢复 | ✅ |
| `CANCELLED` | `SUSPENDED` | 挂失 | ❌ |
| `ACTIVE` | `ACTIVE` | 办证（已有有效证） | ❌ |

---

### 3.2 CardNumber（借阅证号，值对象）

| 项 | 内容 |
|---|---|
| **类型** | 值对象 |
| **职责** | 表示借阅证号，保证格式与唯一性 |

**属性**：`value`（字符串）

**格式**：`CARD` + 4 位年份 + 6 位序号，如 `CARD2026000001`（BR-004）

**关键行为**：

| 方法 | 说明 |
|---|---|
| `generate(year, sequence)` | 按年份与序号生成证号 |
| `parse(value)` | 解析证号，提取年份与序号 |
| `is_valid(value)` | 校验格式合法性 |

**不变量**：必须匹配正则 `^CARD\d{4}\d{6}$`；序号按年递增，每年从 `000001` 开始。

---

### 3.3 CardStatus（借阅证状态，枚举）

| 取值 | 含义 | 可否借书 |
|---|---|:---:|
| `ACTIVE` | 有效 | ✅ |
| `SUSPENDED` | 已挂失/暂停 | ❌ |
| `CANCELLED` | 已注销 | ❌ |
| `EXPIRED` | 已过期（当前不使用） | ❌ |

---

## 4. 书目模块（catalog）

### 4.1 BookTitle（图书标题，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体（聚合根） |
| **职责** | 描述一种图书的题录信息，是馆藏副本的抽象定义 |
| **标识** | `title_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `title_id` | 标识 | 唯一标识 |
| `title` | 字符串 | 题名 |
| `author` | 字符串 | 作者 |
| `isbn` | Isbn | ISBN（值对象，可空） |
| `publisher` | 字符串 | 出版社 |
| `publish_year` | 整数 | 出版年份 |
| `item_type` | ItemType | 借出物类型 |
| `language` | 字符串 | 语种 |
| `is_deleted` | 布尔 | 软删除标记 |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `add_item(barcode)` | 为该标题添加一个馆藏副本 |
| `available_items()` | 返回全部可借副本 |
| `has_available_item()` | 判断是否存在可借副本 |
| `can_be_reserved()` | 判断是否可预约（所有副本均不可借） |
| `remove()` | 软删除本标题及其下副本 |

**约束**：

- `isbn` 若填写则全局唯一。
- 允许在无任何副本的状态下存在（BR-014）。
- 软删除后，其下所有未借出副本同步置为 `REMOVED`；已借出副本待归还后置为 `REMOVED`（BR-042）。
- 软删除后仅系统管理员可见（BR-037）。

**关系**：`BookTitle` 1 — 0..* `LibraryItem`

**重要说明**：`BookTitle` 是**题录信息**（"《算法导论》这本书"），`LibraryItem` 是**物理副本**（"编号 BC00000001 的那一本"）。这个区分是本系统的核心建模决策，直接影响预约逻辑（预约的是标题，借出的是副本）。

---

### 4.2 LibraryItem（馆藏副本，抽象实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体（抽象基类） |
| **职责** | 表示一件具体的、可被借出的馆藏实物 |
| **标识** | `item_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `item_id` | 标识 | 唯一标识 |
| `barcode` | Barcode | 馆藏条码（值对象），全局唯一 |
| `title_id` | 标识 | 所属图书标题 |
| `status` | ItemStatus | 副本状态 |
| `location` | 字符串 | 存放位置 |
| `acquired_at` | 日期 | 入库日期 |
| `price` | Money | 定价 |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `is_available()` | 判断是否为 `AVAILABLE` |
| `mark_borrowed()` | 置为 `BORROWED` |
| `mark_returned(has_reservation)` | 归还时调用：有预约置 `RESERVED`，无预约置 `AVAILABLE` |
| `mark_reserved()` | 置为 `RESERVED` |
| `mark_lost()` | 置为 `LOST` |
| `mark_damaged()` | 置为 `DAMAGED` |
| `remove()` | 置为 `REMOVED` |

**约束**：

- `barcode` 全局唯一（BR-041 格式 `BC` + 8 位数字）。
- 仅 `AVAILABLE` 状态可被借出（BR-033）。
- `BORROWED` 状态不可直接删除，须先归还（BR-034）。

**关系**：`LibraryItem` * — 1 `BookTitle`

---

### 4.3 Book / Magazine / Thesis（具体馆藏类型，实体）

| 类 | 类型 | 说明 | 对应 ItemType |
|---|---|---|---|
| **Book** | `LibraryItem` 子类 | 图书，区分中外文 | `CHINESE_BOOK` / `FOREIGN_BOOK` |
| **Magazine** | `LibraryItem` 子类 | 杂志，区分中外文 | `CHINESE_MAGAZINE` / `FOREIGN_MAGAZINE` |
| **Thesis** | `LibraryItem` 子类 | 学位论文 | `THESIS` |

**设计说明**：

这三类子类**共享相同的属性结构**，差异仅体现在：
1. 罚款单价不同（由 `FineRule` 策略决定）
2. 业务语义不同（杂志通常不可预约、论文不外借等，本项目未启用这些限制）

**因此本系统的建模策略为**：

- **领域模型层**：保留 `LibraryItem` 的继承结构（`Book` / `Magazine` / `Thesis`），用于表达业务分类的语义，并在类图中体现。
- **持久化层**：采用单表继承，`library_items` 表通过 `item_type` 字段区分，不拆分为多张表（决策 D-50）。
- **罚款差异**：由 `FineRule` 策略对象按 `item_type` 查表决定，不在子类中硬编码。

**约束**：`item_type` 必须在五种枚举内；`Book` 和 `Magazine` 各有中外文两种取值。

---

### 4.4 Barcode（馆藏条码，值对象）

| 项 | 内容 |
|---|---|
| **类型** | 值对象 |
| **职责** | 表示馆藏副本的唯一条码 |

**属性**：`value`（字符串）

**格式**：`BC` + 8 位数字，如 `BC00000001`

**关键行为**：`generate(sequence)`、`parse(value)`、`is_valid(value)`

**不变量**：必须匹配正则 `^BC\d{8}$`

---

### 4.5 Isbn（ISBN，值对象）

| 项 | 内容 |
|---|---|
| **类型** | 值对象 |
| **职责** | 表示图书的国际标准书号，可为空 |

**属性**：`value`（字符串，可空）

**关键行为**：`is_valid(value)`、`normalize(value)`

**不变量**：非空时全局唯一。

---

### 4.6 ItemType（借出物类型，枚举）

| 取值 | 中文 | 罚款单价（元/天） |
|---|---|---:|
| `CHINESE_BOOK` | 中文图书 | 0.20 |
| `FOREIGN_BOOK` | 外文图书 | 0.50 |
| `CHINESE_MAGAZINE` | 中文杂志 | 0.10 |
| `FOREIGN_MAGAZINE` | 外文杂志 | 0.20 |
| `THESIS` | 论文 | 1.00 |

> 罚款单价由 `FineRule` 策略对象提供，此处列出便于对照。

---

### 4.7 ItemStatus（副本状态，枚举）

| 取值 | 含义 | 是否可借 |
|---|---|:---:|
| `AVAILABLE` | 在架可借 | ✅ |
| `BORROWED` | 已借出 | ❌ |
| `RESERVED` | 已预留（给预约者） | ❌ |
| `LOST` | 已丢失 | ❌ |
| `DAMAGED` | 已破损 | ❌ |
| `REMOVED` | 已下架/注销 | ❌ |

---

## 5. 流通模块（circulation）

### 5.1 Loan（借阅记录，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体（聚合根） |
| **职责** | 记录一次借阅的全生命周期：借出、续借、归还、超期判定 |
| **标识** | `loan_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `loan_id` | 标识 | 唯一标识 |
| `reader_id` | 标识 | 借阅人 |
| `item_id` | 标识 | 被借出的馆藏副本 |
| `borrowed_at` | 时间戳 | 借出时刻 |
| `due_at` | 时间戳 | 应归还时刻 |
| `returned_at` | 时间戳 | 实际归还时刻（可空） |
| `status` | LoanStatus | 状态 |
| `librarian_id` | 标识 | 经办图书管理员 |
| `renew_count` | 整数 | 已续借次数（0-2） |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `create(reader, item, policy, librarian)` | 创建借阅记录，按读者类型设置 `due_at` |
| `is_overdue(now)` | 判断当前是否超期（`returned_at` 为空且 `now` > `due_at`） |
| `overdue_days(now)` | 计算逾期天数（向上取整） |
| `can_renew()` | 判断是否可续借（未超期、续借次数 < 2、额度未超） |
| `renew()` | 续借：`due_at` + 7 天，`renew_count` + 1 |
| `return_item(now)` | 归还：设置 `returned_at`，状态置为 `RETURNED` |

**约束**：

- 续借次数最多 2 次，每次延长固定 7 天（BR-015）。
- 已超期的记录不可续借（BR-016）。
- 续借不额外占用借阅额度（BR-019）。
- 存在预约排队不影响续借（BR-018）。
- 经办图书管理员必须记录（BR-018 对应决策 D-18）。

**关系**：

- `Loan` * — 1 `Reader`
- `Loan` * — 1 `LibraryItem`
- `Loan` * — 1 `Librarian`（经办人）
- `Loan` 1 — 0..1 `FineRecord`（超期时生成）

**状态机**：

```
     借出
   ──────→ BORROWED ──────────→ RETURNED
              │
              │ 超过 due_at
              ↓
           OVERDUE ──────────→ RETURNED
```

| 状态 | 含义 | 是否占用额度 |
|---|---|:---:|
| `BORROWED` | 已借出，未超期 | ✅ |
| `OVERDUE` | 已借出，已超期 | ✅ |
| `RETURNED` | 已归还 | ❌ |

**设计说明**：`OVERDUE` 是 `BORROWED` 的**派生状态**，可由 `due_at` 与当前时间实时判定，无须持久化。持久化层可仅存 `BORROWED` / `RETURNED`，查询时计算超期。本模型保留 `OVERDUE` 作为领域概念，便于业务表达与测试断言。

---

### 5.2 DateRange（时间区间，值对象）

| 项 | 内容 |
|---|---|
| **类型** | 值对象 |
| **职责** | 表示借出到应归还的时间区间 |

**属性**：`start`（时间戳）、`end`（时间戳）

**关键行为**：

| 方法 | 说明 |
|---|---|
| `contains(moment)` | 判断某个时刻是否在区间内 |
| `days()` | 返回区间天数 |
| `extend_days(days)` | 延长区间，返回新的 `DateRange`（不可变） |

**不变量**：`start` ≤ `end`

**不可变性**：`extend_days` 返回新对象，不修改原对象。

---

### 5.3 LoanStatus（借阅状态，枚举）

| 取值 | 含义 |
|---|---|
| `BORROWED` | 已借出，未超期 |
| `OVERDUE` | 已借出，已超期 |
| `RETURNED` | 已归还 |

---

### 5.4 BorrowEligibilityService（借阅资格判定服务，领域服务）

| 项 | 内容 |
|---|---|
| **类型** | 领域服务 |
| **职责** | 判定读者是否满足借书条件。跨 `Reader`、`BorrowCard`、`Loan`、`Reservation`、`FineRecord` 多个实体 |

**关键方法**：

| 方法 | 说明 |
|---|---|
| `check_eligibility(reader, card, loans, reservations, fines, policy)` | 综合判定借书资格，返回校验结果列表 |
| `validate_card(card)` | 校验借阅证有效性 |
| `check_quota(reader, loans, reservations, policy)` | 校验借阅数量 |
| `check_overdue(loans, now)` | 校验是否存在超期未还 |
| `check_unpaid_fine(fines)` | 校验是否存在未缴罚款 |

**校验顺序（固定）**：权限 → 借阅证 → 数量 → 超期 → 罚款 → 副本

**说明**：本服务是"纯函数式"的——不修改任何实体状态，只做判定并返回结果。这是它与应用服务的关键区别。

**为什么是领域服务而非实体的方法**：借阅资格判定需要同时访问读者、借阅证、借阅记录、预约、罚款五类对象，放在任何单一实体中都会造成职责错位和数据加载负担。

---

### 5.5 RenewalService（续借服务，领域服务）

| 项 | 内容 |
|---|---|
| **类型** | 领域服务 |
| **职责** | 判定续借资格并执行续借 |

**关键方法**：

| 方法 | 说明 |
|---|---|
| `can_renew(loan, reader, loans, reservations, policy, now)` | 判定是否可续借 |
| `renew(loan, days)` | 执行续借 |

**约束**：判定条件为「未超期」且「续借次数 < 2」且「未超出借阅额度」（BR-015 ~ BR-018）。

---

## 6. 预约模块（reservation）

### 6.1 Reservation（预约，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体（聚合根） |
| **职责** | 记录读者对某图书标题的预约，支持排队与到书预留 |
| **标识** | `reservation_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `reservation_id` | 标识 | 唯一标识 |
| `reader_id` | 标识 | 预约人 |
| `title_id` | 标识 | 预约的图书标题 |
| `created_at` | 时间戳 | 创建时刻（决定排队顺序） |
| `status` | ReservationStatus | 状态 |
| `ready_at` | 时间戳 | 到书可借时刻（可空） |
| `expired_at` | 时间戳 | 失效时刻（可空） |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `create(reader, title)` | 创建预约，状态 `ACTIVE` |
| `mark_ready(now)` | 副本已预留，状态置为 `READY`，记录 `ready_at` |
| `cancel()` | 取消，状态置为 `CANCELLED` |
| `expire(now)` | 失效，状态置为 `EXPIRED` |
| `is_active()` | 判断是否占用额度（`ACTIVE` 或 `READY`） |
| `queue_position(reservations)` | 计算在队列中的位置（按 `created_at` 升序） |
| `is_expired(now, validity_days)` | 判断是否已超过有效期 |

**约束**：

- 同一读者对同一标题不得存在多个有效预约（BR-023）。
- 每个标题的队列上限 5 人（BR-022）。
- 仅在标题下所有副本均不可借时才可预约（BR-020）。
- 有效期 7 天：`ACTIVE` 自 `created_at` 起算，`READY` 自 `ready_at` 起算（BR-025）。
- 有效预约占用 1 个借阅额度，取消或失效后释放（BR-026）。
- **`RESERVED` 副本的归属始终跟随队列头部的有效预约**：队首失效或取消时，副本转交下一位（对方 `ACTIVE` → `READY`，副本仍为 `RESERVED`）；队列无有效预约时才释放为 `AVAILABLE`（BR-024a）。
- **有效预约（`ACTIVE` 或 `READY`）均可由读者主动取消**；取消 `READY` 预约时副本按上述规则转交（BR-025a）。
- 预约超期采用**惰性判定**（查询或操作时计算）。但判定出超期后，**必须在同一次操作内**完成队列顺延与副本交接，不得遗留无人接管的 `RESERVED` 副本（BR-025b）。

**关系**：

- `Reservation` * — 1 `Reader`
- `Reservation` * — 1 `BookTitle`

**状态机**：

```
                 创建
      ──────────────→ ACTIVE ──────→ READY ──────→ EXPIRED
                        │              │
                        │ 取消          │ 取消/超期未取
                        ↓              ↓
                    CANCELLED      CANCELLED / EXPIRED
                        │
                        │ 7 天未借到
                        ↓
                     EXPIRED
```

| 状态 | 含义 | 是否占额度 | 是否在队列中 |
|---|---|:---:|:---:|
| `ACTIVE` | 排队等待中 | ✅ | ✅ |
| `READY` | 已到书，待读者借取 | ✅ | ✅（队首） |
| `EXPIRED` | 已失效 | ❌ | ❌ |
| `CANCELLED` | 已取消 | ❌ | ❌ |

---

### 6.2 ReservationStatus（预约状态，枚举）

| 取值 | 含义 |
|---|---|
| `ACTIVE` | 排队等待中 |
| `READY` | 已到书，待借取 |
| `EXPIRED` | 已失效 |
| `CANCELLED` | 已取消 |

---

### 6.3 ReservationQueueService（预约队列服务，领域服务）

| 项 | 内容 |
|---|---|
| **类型** | 领域服务 |
| **职责** | 管理预约队列：排序、上限校验、队首识别、失效顺延 |

**关键方法**：

| 方法 | 说明 |
|---|---|
| `enqueue(reservation, existing_queue, max_size)` | 入队，校验队列上限 |
| `peek(reservations)` | 返回队首的有效预约 |
| `position_of(reservation, reservations)` | 计算指定预约的排队位置 |
| `dequeue_expired(reservations, now, validity_days)` | 清理失效预约，返回队列顺延结果 |
| `can_reserve(title, existing_reservations)` | 判断是否可预约（含队列上限与重复校验） |

**约束**：

- 队列顺序由 `created_at` 升序决定（BR-021）。
- 队列上限 5 人（BR-022）。
- 队列的并发安全由应用层事务保证。

---

## 7. 罚款模块（fine）

### 7.1 FineRecord（罚款记录，实体）

| 项 | 内容 |
|---|---|
| **类型** | 实体 |
| **职责** | 记录一次超期罚款的产生与缴纳 |
| **标识** | `fine_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `fine_id` | 标识 | 唯一标识 |
| `loan_id` | 标识 | 关联的借阅记录 |
| `reader_id` | 标识 | 被罚款的读者 |
| `amount` | Money | 罚款金额（值对象） |
| `overdue_days` | 整数 | 逾期天数 |
| `billed_days` | 整数 | 计罚天数（扣除宽限期后） |
| `unit_price` | Money | 计算时使用的单价（快照） |
| `status` | FineStatus | 缴纳状态 |
| `created_at` | 时间戳 | 产生时刻 |
| `paid_at` | 时间戳 | 缴纳时刻（可空） |
| `operator_id` | 标识 | 收缴经办人（可空） |
| `operator_role` | 枚举 | 收缴人角色（`LIBRARIAN` / `ADMIN`，可空）。因收缴人可能来自 `librarians` 或 `system_admins` 两张表，需以角色标识消歧 |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `create(loan, item_type, returned_at, fine_rule)` | 按罚款规则计算并创建罚款记录 |
| `pay(operator)` | 标记已缴纳 |
| `is_unpaid()` | 判断是否为未缴状态 |

**约束**：

- 单笔罚款封顶 100 元（BR-030）。
- 罚款在还书时一次性计算（BR-029）。
- 已生成的罚款不因规则修改而变化（BR-050）。
- 金额计算使用 `Decimal`，不得用浮点数（对应 Q-04）。

**关系**：

- `FineRecord` 1 — 1 `Loan`
- `FineRecord` * — 1 `Reader`
- `FineRecord` * — 1 `Librarian` 或 `SystemAdmin`（收缴人）

---

### 7.2 Money（金额，值对象）

| 项 | 内容 |
|---|---|
| **类型** | 值对象 |
| **职责** | 表示金额，保证精度与币种 |

**属性**：`amount`（Decimal，精确到分）、`currency`（默认 `CNY`）

**关键行为**：

| 方法 | 说明 |
|---|---|
| `multiply(factor)` | 乘以天数，返回新 `Money` |
| `min_with_cap(cap)` | 与封顶金额比较取小 |
| `is_zero()` | 判断是否为零 |
| `__add__` / `__sub__` | 支持金额加减 |

**不变量**：

- `amount` 使用 `Decimal` 类型，**禁止**使用 `float`。
- `amount` 精确到 2 位小数。
- `amount` 非负。

**为什么是值对象**：金额无身份标识，两个 100.00 元是同一个概念。

---

### 7.3 FineStatus（罚款状态，枚举）

| 取值 | 含义 |
|---|---|
| `UNPAID` | 未缴纳 |
| `PAID` | 已缴纳 |

---

## 8. 规则模块（policy）

### 8.1 BorrowPolicy（借阅策略，策略对象）

| 项 | 内容 |
|---|---|
| **类型** | 策略对象（Strategy 模式的领域侧体现） |
| **职责** | 定义各读者类型的借阅额度与期限，可在线维护 |
| **标识** | `policy_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `policy_id` | 标识 | 唯一标识 |
| `reader_type` | ReaderType | 适用的读者类型 |
| `max_borrow_count` | 整数 | 最大借阅数量 |
| `borrow_days` | 整数 | 借阅期限（天） |
| `updated_at` | 时间戳 | 最后修改时间 |
| `updated_by` | 标识 | 最后修改人 |

**数据表（初始值）**：

| reader_type | max_borrow_count | borrow_days |
|---|---:|---:|
| `COLLEGE` | 5 | 30 |
| `UNDERGRADUATE` | 5 | 30 |
| `GRADUATE` | 10 | 60 |
| `DOCTOR` | 15 | 90 |
| `TEACHER` | 20 | 90 |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `limit_for(reader_type)` | 查询指定读者类型的最大借阅数量 |
| `days_for(reader_type)` | 查询指定读者类型的借阅期限 |
| `update(max_count, days, operator)` | 更新规则，记录操作人与时间 |

**约束**：

- 数值必须为正整数（BR-006）。
- 规则**必须**存储在数据库中，**严禁**硬编码为代码常量（BR-049）。
- 修改即时生效，但**不追溯**已存在的借阅记录（`due_at` 在借阅时已快照）（BR-050）。

**设计说明**：`BorrowPolicy` 是本系统 **Strategy 模式的落点之一**。不同读者类型的规则差异通过查表体现，而非在代码中写 `if reader_type == ...` 分支。

---

### 8.2 FineRule（罚款规则，策略对象）

| 项 | 内容 |
|---|---|
| **类型** | 策略对象 |
| **职责** | 定义各借出物类型的罚款单价，以及宽限期与封顶，可在线维护 |
| **标识** | `rule_id` |

**关键属性**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `rule_id` | 标识 | 唯一标识 |
| `item_type` | ItemType | 适用的借出物类型 |
| `daily_price` | Money | 日罚款单价 |
| `grace_days` | 整数 | 宽限期天数 |
| `max_amount` | Money | 单笔封顶金额 |
| `updated_at` | 时间戳 | 最后修改时间 |
| `updated_by` | 标识 | 最后修改人 |

**数据表（初始值）**：

| item_type | daily_price | grace_days | max_amount |
|---|---:|---:|---:|
| `CHINESE_BOOK` | 0.20 | 2 | 100.00 |
| `FOREIGN_BOOK` | 0.50 | 2 | 100.00 |
| `CHINESE_MAGAZINE` | 0.10 | 2 | 100.00 |
| `FOREIGN_MAGAZINE` | 0.20 | 2 | 100.00 |
| `THESIS` | 1.00 | 2 | 100.00 |

**关键行为**：

| 方法 | 说明 |
|---|---|
| `calculate_fine(item_type, overdue_days)` | 计算罚款金额 |
| `billed_days(overdue_days)` | 计算计罚天数 = max(overdue_days - grace_days, 0) |
| `update(daily_price, grace_days, max_amount, operator)` | 更新规则 |

**计算规则**：

```
billed_days = max(overdue_days - grace_days, 0)
amount = min(billed_days × daily_price, max_amount)
```

**计算示例**（中文图书）：

| 逾期天数 | 计罚天数 | 罚款金额 |
|---:|---:|---:|
| 0-2 | 0 | 0.00 |
| 3 | 1 | 0.20 |
| 10 | 8 | 1.60 |
| 100 | 98 | 19.60 |
| 1000 | 998 | 100.00（封顶） |

**约束**：

- `daily_price` 必须为非负数；`grace_days` 与 `max_amount` 必须为非负整数（BR-028）。
- 规则**必须**存储在数据库中，**严禁**硬编码（BR-049）。
- 修改**不追溯**已生成的罚款记录（BR-050）。

**设计说明**：`FineRule` 是本系统 **Strategy 模式的另一个落点**。不同借出物类型的罚款差异通过查表体现。

---

## 9. 领域模型关系总表

### 9.1 继承关系

| 子类 | 父类 | 说明 |
|---|---|---|
| `StudentReader` | `Reader` | 学生读者 |
| `TeacherReader` | `Reader` | 教师读者 |
| `Book` | `LibraryItem` | 图书 |
| `Magazine` | `LibraryItem` | 杂志 |
| `Thesis` | `LibraryItem` | 论文 |

### 9.2 关联关系

| 源 | 目标 | 多重性 | 说明 |
|---|---|---|---|
| `Reader` | `BorrowCard` | 1 — 0..1 | 一个读者最多一张有效借阅证 |
| `Reader` | `Loan` | 1 — 0..* | 一个读者有多条借阅记录 |
| `Reader` | `Reservation` | 1 — 0..* | 一个读者有多个预约 |
| `Reader` | `FineRecord` | 1 — 0..* | 一个读者有多条罚款记录 |
| `BookTitle` | `LibraryItem` | 1 — 0..* | 一个标题有零到多个副本（组合） |
| `LibraryItem` | `Loan` | 1 — 0..* | 一个副本有多条历史借阅记录 |
| `Loan` | `FineRecord` | 1 — 0..1 | 一条借阅记录最多产生一条罚款 |
| `Loan` | `Librarian` | * — 1 | 每条借阅记录由一名图书管理员经办 |
| `Reservation` | `BookTitle` | * — 1 | 预约针对标题 |
| `BookTitle` | `Reservation` | 1 — 0..* | 一个标题有多条预约（队列） |
| `BorrowCard` | `SystemAdmin` | * — 1 | 借阅证由系统管理员签发 |
| `FineRecord` | `Librarian` / `SystemAdmin` | * — 1 | 罚款由图书管理员或管理员收缴 |

### 9.3 依赖关系（领域服务与策略）

| 使用方 | 被使用方 | 说明 |
|---|---|---|
| `BorrowEligibilityService` | `BorrowPolicy` | 借阅资格判定需查询额度规则 |
| `Loan` | `BorrowPolicy` | 创建借阅记录时按政策设置 `due_at` |
| `RenewalService` | `BorrowPolicy` | 续借判定需查询额度 |
| `FineRecord` | `FineRule` | 罚款计算依赖规则 |
| `ReservationQueueService` | `Reservation` | 队列管理操作预约实体 |

---

## 10. 关键领域规则摘要

> 完整的业务规则见 `02-requirements.md` 第 3 节（BR-001 ~ BR-050 及后缀条目 BR-024a/025a/025b）。此处摘录与领域模型直接相关的核心规则。

| 规则 | 内容 | 承载对象 |
|---|---|---|
| 借阅额度 | 按读者类型区分（5/5/10/15/20 册） | `BorrowPolicy` → `Reader.borrow_limit()` |
| 借阅期限 | 按读者类型区分（30/30/60/90/90 天） | `BorrowPolicy` → `Loan.due_at` |
| 额度占用 | 未归还借阅 + 有效预约 | `Reader.occupies_quota()` |
| 续借 | 最多 2 次，每次 +7 天 | `RenewalService` → `Loan.renew()` |
| 禁借条件 | 有超期未还 或 有未缴罚款 | `BorrowEligibilityService` |
| 可预约条件 | 该标题所有副本均不可借 | `BookTitle.can_be_reserved()` |
| 预约队列 | 按 `created_at` 升序，上限 5 人 | `ReservationQueueService` |
| 预约预留 | 还书时队首预约置 `READY`，副本置 `RESERVED` | `LibraryItem.mark_returned()` |
| 预约交接 | 队首失效或取消时，`RESERVED` 副本转交下一位（对方 `ACTIVE` → `READY`）；队列无有效预约才释放为 `AVAILABLE` | `ReservationQueueService` |
| 预约取消 | `ACTIVE` 与 `READY` 状态均可由读者主动取消；取消 `READY` 时副本按上一条交接 | `Reservation.cancel()` |
| 罚款计算 | `min(max(逾期天数-宽限期,0) × 单价, 封顶)` | `FineRule.calculate_fine()` |
| 罚款封顶 | 单笔 100 元 | `FineRule` |
| 软删除 | 全部删除为软删除，仅系统管理员可见 | 各实体的 `is_deleted` / `REMOVED` |

---

## 11. 人工审查重点自查

> 对照实验一第十二节列出的人工审查重点，逐条自查。

| 审查项 | 自查结果 |
|---|---|
| 领域类是否来自业务，不是数据库表的机械翻译？ | ✅ 全部领域类对应业务概念。例如 `BookTitle`（题录）与 `LibraryItem`（物理副本）的分离来自"同一本书可有多本实体"的业务事实，而非表设计推导。 |
| 是否体现不同读者类型？ | ✅ `Reader` ← `StudentReader` / `TeacherReader`，且 `StudentReader` 按学历细分四种类型。 |
| 是否体现不同借出物类型？ | ✅ `LibraryItem` ← `Book` / `Magazine` / `Thesis`，`ItemType` 枚举细分五种。 |
| 借阅规则是否抽象为 `BorrowPolicy`？ | ✅ `BorrowPolicy` 为策略对象，规则存数据库，`Reader.borrow_limit()` 委托查询。 |
| 罚款规则是否抽象为 `FineRule`？ | ✅ `FineRule` 为策略对象，`FineRecord.create()` 依赖其计算。 |
| `Loan` 是否能表达借出和归还状态？ | ✅ `LoanStatus` 枚举含 `BORROWED` / `OVERDUE` / `RETURNED`，`returned_at` 可空。 |
| `Reservation` 是否支持排队？ | ✅ 以 `created_at` 排序，`ReservationQueueService` 提供 `queue_position()`，状态含 `ACTIVE` → `READY` 流转。 |
| 是否过早引入 Controller、Repository、DTO？ | ✅ 本文件**不含**任何设计类，全部为领域概念。 |

---

## 12. 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|---|---|---|---|
| v1.0 | 2026-09-19 | 初版制定。14 个实体、12 个值对象/枚举、3 个领域服务、2 个策略对象。 | Agent 起草 |
| v1.1 | 2026-09-19 | ① 修正对象计数（v1.0 误写 11 个实体 / 13 个值对象，实际 14 / 12）并补充计数口径说明；② `FineRecord` 补 `operator_role` 字段，与 `13-database-design.md` §4.9 同步；③ 补充预约交接与取消规则（BR-024a / 025a / 025b）。 | Agent 自检后修订 |
