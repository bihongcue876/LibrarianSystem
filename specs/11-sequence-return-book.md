# 顺序图：办理还书（UC-102）

> **文档编号**：`specs/11-sequence-return-book.md`
> **制定依据**：`03-use-cases.md`（UC-102、UC-102a）、`09-design-model.md`（§3、§8）
> **版本**：v1.0
> **日期**：2026-09-20
>
> **绘图工具**：实验文档建议 `11-sequence-return-book.puml`；本项目依 `constitution.md` 第三条改用 **Mermaid**，故扩展名为 `.md`（理由见 `10-sequence-borrow-book.md` 头部说明）。
>
> **参与对象对应**：`circulation_router` = `LibrarianController`；`CatalogRepository` = `LibraryItemRepository`；`FineRule` = `FineRuleService`；罚款计算在本项目内聚于 `CirculationService` + `FineRule`，不单设 `FineService`（理由见 `09-design-model.md` §1.3）。

---

## 1. 正常流程、异常分支与罚款计算

```mermaid
sequenceDiagram
    autonumber
    actor L as 图书管理员
    participant C as circulation_router
    participant S as CirculationService
    participant IT as CatalogRepository
    participant LN as LoanRepository
    participant PO as PolicyRepository
    participant FL as FineRule
    participant FR as FineRepository
    participant RS as ReservationRepository
    participant QS as ReservationQueueService
    participant I as LibraryItem
    participant LO as Loan
    participant FD as FineRecord
    participant RV as Reservation

    L->>C: POST /api/circulation/return  barcode
    C->>C: require_role(LIBRARIAN, SYSTEM_ADMIN)
    Note over C: 仅凭馆藏条码，无需借阅证
    C->>S: return_book(request, operator)
    S->>S: 开启事务 UnitOfWork

    S->>IT: find_by_barcode(barcode)
    IT-->>S: LibraryItem 或 空

    alt 馆藏条码不存在
        S-->>C: NotFoundError ITEM_NOT_FOUND
        C-->>L: 404 非本馆藏书
    else 副本存在
        S->>LN: find_active_by_item(item_id)
        LN-->>S: Loan 或 空

        alt 找不到未归还的借阅记录
            S-->>C: NotFoundError LOAN_NOT_FOUND
            C-->>L: 404 未找到该副本的在借记录
        else 找到未归还借阅记录
            S->>LO: overdue_days(now)
            LO-->>S: 超期天数

            alt 超期天数大于 0
                S->>PO: get_fine_rule(item_type)
                PO-->>S: FineRule
                S->>FL: billed_days(overdue_days)
                Note over FL: 计罚天数 = 超期天数 - 宽限天数（宽限默认 2 天）<br/>不足宽限则计罚 0 天
                FL-->>S: 计罚天数
                S->>FL: calculate_fine(item_type, overdue_days)
                Note over FL: 金额 = 计罚天数 × 单价，且不超过封顶 100.00 元<br/>全程使用 Decimal，禁止 float
                FL-->>S: Money 金额
                S->>FD: create(loan, item_type, returned_at, fine_rule)
                Note over FD: 快照 unit_price<br/>规则修改不追溯（BR-050）
                FD-->>S: FineRecord 状态 UNPAID
            else 未超期
                Note over S: 不创建罚款记录
            end

            S->>LO: return_item(now)
            Note over LO: status → RETURNED，写入 returned_at
            S->>RS: find_active_by_title(title_id)
            RS-->>S: 预约队列

            alt 队列中存在有效预约
                S->>QS: peek(reservations)
                QS-->>S: 队首预约
                S->>RV: mark_ready(now)
                Note over RV: ACTIVE → READY，写入 ready_at
                S->>I: mark_reserved()
                Note over I: 副本置 RESERVED，等待队首读者取书（BR-024a）
                S->>RS: update(reservation)
            else 队列为空
                S->>I: mark_returned(has_reservation=false)
                Note over I: 副本置 AVAILABLE 可再借
            end

            S->>QS: dequeue_expired(reservations, now, validity_days)
            Note over QS: 惰性失效判定 + 队列顺延<br/>须在同一次操作内完成（BR-025b）
            QS-->>S: 顺延后的队列状态

            S->>LN: update(loan)
            S->>IT: update(item)
            opt 存在罚款
                S->>FR: add(fine_record)
            end
            S->>S: 提交事务
            S-->>C: ReturnBookResponse
            C-->>L: 200 归还成功 罚款金额 + 副本去向
        end
    end
```

---

## 2. 与用例文本的对应关系

| 用例步骤（UC-102） | 图中体现 | 判定 |
|---|---|---|
| 输入馆藏条码（不要求借阅证） | 第 1 条消息 + `Note over C` | ✅ |
| 验证馆藏副本存在 | `find_by_barcode` + `ITEM_NOT_FOUND` 分支 | ✅ |
| 查找未归还 `Loan` | `find_active_by_item` + `LOAN_NOT_FOUND` 分支 | ✅ |
| 设置归还时间 | `Loan.return_item(now)` 写入 `returned_at` | ✅ |
| 更新 `Loan` 状态为 `RETURNED` | 同上 | ✅ |
| 更新 `LibraryItem` 状态 | `mark_returned` / `mark_reserved` 两分支 | ✅ |
| 超期则生成 `FineRecord` | `alt 超期天数大于 0` 分支链 | ✅ |
| 处理预约预留 | `peek` → `mark_ready` → `mark_reserved` | ✅ |

**异常覆盖核对**（实验二步骤 3 要求）：

| 要求表达的异常 | 图中分支 |
|---|---|
| 图书不是本馆藏书 | 外层 `alt` 第 1 分支（`ITEM_NOT_FOUND`，404） |
| 找不到借阅记录 | 内层 `alt` 第 1 分支（`LOAN_NOT_FOUND`，404） |
| 超期罚款计算流程 | 内层 `alt` 第 1 分支完整计算链（含宽限与封顶说明） |

**与 UC-102a 的关系**：UC-102a「计算超期罚款」被 UC-102 **include**，因此在图中**不出现独立的调用入口**，而是以内嵌分支的形式呈现（`04-use-case-model.md` 图 5 已表达该 include 关系）。

---

## 3. 计算示例（用于核对图与规则的一致性）

| 应还日期 | 归还日期 | 超期天数 | 计罚天数 | 单价（外文书） | 金额 |
|---|---|---:|---:|---:|---:|
| 2026-09-10 | 2026-09-11 | 1 | 0 | 0.50 | 0.00 |
| 2026-09-10 | 2026-09-12 | 2 | 0 | 0.50 | 0.00 |
| 2026-09-10 | 2026-09-13 | 3 | 1 | 0.50 | 0.50 |
| 2026-09-10 | 2026-10-01 | 21 | 19 | 0.50 | 9.50 |
| 2026-09-10 | 2027-09-10 | 365 | 363 | 1.00 | 100.00（封顶） |

---

## 4. 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|---|---|---|---|
| v1.0 | 2026-09-20 | 初版制定。含正常流程、2 个异常分支、超期罚款完整计算链与预约预留分支；附 5 行金额计算示例。 | Agent 起草 |
