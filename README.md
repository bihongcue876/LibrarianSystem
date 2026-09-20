# AI时代图书管理系统

> 《软件设计与体系结构》课程实验 —— 图书管理系统的规格驱动（Spec-Driven）实现。
>
> 实验一交付需求、用例、领域模型、架构与数据库设计规格；**实验二**交付详细设计、接口规范、测试设计与后端实现。

---

## 1. 项目简介

一个面向高校图书馆的**借阅流通管理系统**，覆盖读者管理、借阅证管理、书目与馆藏管理、借还流通、预约排队、超期罚款、规则维护与统计。

系统以 **Agent 辅助 + 人工审查**的方式开发：规格（`specs/`）由 Agent 起草、人工拍板并冻结，代码严格按规格实现，架构约束（分层、依赖方向、规则不硬编码）由**自动化测试**守护。

**范围说明**：实验二不含前端实现环节，验收标准以「借书、还书、预约、查询至少可用」+ 自动化测试通过为准，故本期交付为**后端 REST API**。前端技术约定见 §3。

---

## 2. 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 语言 | Python | **3.14** |
| Web 框架 | FastAPI | ≥ 0.115 |
| 数据校验 / DTO | Pydantic | ≥ 2.x |
| ORM | SQLAlchemy | ≥ 2.x |
| 数据库 | SQLite | 内置 |
| 密码哈希 | bcrypt | ≥ 4.1 |
| 令牌 | PyJWT | ≥ 2.8 |
| 测试 | pytest + httpx | ≥ 8.x |
| **后端依赖管理** | **uv** | ≥ 0.5 |
| **前端包管理**（约定） | **pnpm** | ≥ 9 |

**为什么用 uv**：可直接安装并固定 Python 解释器版本（本项目需 3.14）、锁文件覆盖传递依赖、解析安装更快。
`pyproject.toml` + `uv.lock` 是唯一依赖来源，**不使用 `requirements.txt`**。

---

## 3. 架构说明

### 3.1 四层分层

```
presentation/  表现层  路由（Controller）、DTO、鉴权守卫
      ↓
application/   应用层  应用服务、Repository 接口（ports）、事务边界
      ↓
domain/        领域层  实体、值对象、领域服务、策略对象、工厂  ← 零框架依赖
      ↑
infrastructure/ 基础设施层  ORM、Repository 实现、Mapper、安全适配器
```

**依赖方向**：`presentation → application → domain`；`infrastructure` 实现上层定义的接口并由 `presentation/dependencies.py` 注入（依赖倒置）。

### 3.2 分层约束（由测试守护，不靠人工检查）

| 编号 | 约束 | 守护测试 |
|---|---|---|
| R-1 | 路由不得依赖 `infrastructure` | `test_routers_do_not_import_infrastructure` |
| R-2 | 应用层不得依赖 `infrastructure`（`dependencies.py` 是唯一装配点） | `test_application_does_not_import_infrastructure` |
| R-3 | 领域层零框架依赖，只允许标准库与本包 | `test_domain_imports_no_framework_or_outer_layer` |
| D-7 | 实体不得依赖领域服务与工厂 | `test_entities_do_not_depend_on_services_or_factories` |
| BR-049 | 规则数值不得硬编码在代码中 | `test_policies_have_no_rule_literals` |

这些检查用 `ast` 解析**真实的 import 语句**，而非字符串匹配——后者会把 docstring 里对约束的说明误判为违规。

### 3.3 关键设计决策

| 决策 | 理由 |
|---|---|
| 领域实体与 ORM 模型**分离**，用 Mapper 转换 | 领域层不得 `import sqlalchemy`；实体需要行为方法，ORM 模型不该有 |
| 金额列存 **TEXT**（`MoneyType`） | SQLite 无原生 DECIMAL，`Numeric` 会降级为 REAL，重新引入浮点误差（`0.20 × 3 ≠ 0.60`） |
| `loans.status` **只存两态**（`BORROWED` / `RETURNED`） | `OVERDUE` 是派生状态（由 `due_at` 判定），持久化会带来"无人负责的状态陈旧" |
| 规则存库 + **策略对象查表** | `if reader_type == "UNDERGRADUATE": return 5` 这类分支被禁止（BR-049），规则可在线维护 |
| `due_at` / `unit_price` **生成时快照** | 规则修改不追溯已有记录（BR-050），应用层无须额外判断 |
| 事务边界**只在应用服务层** | 事务范围显式可见；Repository 只读写不提交 |
| 三个**部分唯一索引** | 借阅证仅对 `ACTIVE`/`SUSPENDED` 唯一；ISBN 仅对活跃题录唯一（允许已下架书重新采购）；预约仅对有效记录唯一 |

---

## 4. 目录结构

```
expr_proj/
├── specs/                       # 规格文档（实验一 + 实验二）
│   ├── constitution.md          # 开发宪法
│   ├── 00~08                    # 实验一：需求、用例、领域模型、架构、包图
│   ├── 09~12                    # 实验二：详细设计模型、3 张顺序图
│   ├── 13                       # 数据库设计
│   ├── 14~16                    # 实验二：API 规范、测试计划、任务拆解
│   └── 17~19                    # 风险分析、审查清单、AI 使用记录
├── backend/
│   ├── app/
│   │   ├── main.py              # 应用入口、全局异常处理器、CORS
│   │   ├── presentation/        # 表现层
│   │   │   ├── routers/         # 7 个路由模块（Controller）
│   │   │   ├── schemas/         # Pydantic DTO
│   │   │   ├── dependencies.py  # 鉴权守卫 + 服务装配（依赖倒置落点）
│   │   │   └── serializers.py   # 时间序列化辅助
│   │   ├── application/         # 应用层
│   │   │   ├── services/        # 7 个应用服务
│   │   │   ├── ports/           # 7 个 Repository + 2 个安全能力接口
│   │   │   ├── unit_of_work.py  # 事务边界
│   │   │   └── exceptions.py
│   │   ├── domain/              # 领域层（零框架依赖）
│   │   │   ├── entities/        # 14 个实体
│   │   │   ├── value_objects/   # 5 个值对象
│   │   │   ├── enums/           # 7 个枚举
│   │   │   ├── domain_services/ # 3 个领域服务
│   │   │   ├── policies/        # 2 个策略对象
│   │   │   ├── factories/       # 2 个工厂
│   │   │   └── exceptions.py
│   │   └── infrastructure/      # 基础设施层
│   │       ├── db/              # Base、MoneyType、会话工厂
│   │       ├── models/          # 7 组 ORM 模型 → 11 张表
│   │       ├── mappers/         # ORM ↔ 领域对象转换
│   │       ├── repositories/    # 7 个 Repository 实现
│   │       └── security/        # bcrypt、JWT、适配器
│   ├── scripts/init_db.py       # 建表 + 播种规则 + 创建首个系统管理员
│   ├── tests/
│   │   ├── conftest.py          # 共享夹具
│   │   ├── unit/                # 领域层单测（不依赖 DB 与 Web 框架）
│   │   └── integration/         # API 端到端 + 分层约束校验
│   ├── pyproject.toml           # 依赖清单（uv）
│   ├── uv.lock                  # 锁文件（提交 Git）
│   └── .python-version          # 3.14
├── frontend/                    # 前端（本期未实现，包管理约定为 pnpm）
├── worklog.md                   # Agent 行为时序记录
└── README.md
```

---

## 5. 启动方式

### 5.1 准备环境

```bash
# 安装 uv（若未安装）
#   Windows:  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
#   macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh

cd backend

# 安装 Python 3.14 并同步依赖（自动创建 .venv）
uv python install 3.14
uv sync
```

### 5.2 初始化数据库

```bash
# 建表 + 播种借阅规则与罚款规则 + 创建首个系统管理员
# 密码必须显式传入，无默认值（初始化密码不硬编码）
uv run python scripts/init_db.py --admin-username admin --admin-name 系统管理员 --admin-password <你的密码>
```

初始化脚本会写入：

- 5 条借阅规则（专科/本科 5 册 30 天、研究生 10 册 60 天、博士 15 册 90 天、教师 20 册 90 天）
- 5 条罚款规则（中文书 0.20、外文书 0.50、中文杂志 0.10、外文杂志 0.20、论文 1.00 元/天；宽限 2 天，单笔封顶 100 元）
- 1 个系统管理员账号

### 5.3 启动服务

```bash
uv run uvicorn app.main:app --reload --port 8000
```

- 服务地址：http://127.0.0.1:8000
- 交互式 API 文档（Swagger UI）：http://127.0.0.1:8000/docs
- OpenAPI 契约：http://127.0.0.1:8000/openapi.json
- 健康检查：`GET /api/health`

### 5.4 环境变量（可选）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LIBRARY_DATABASE_URL` | `sqlite:///backend/library.db` | 数据库连接串 |
| `LIBRARY_DB_PATH` | `backend/library.db` | SQLite 文件路径 |
| `LIBRARY_JWT_SECRET` | 开发用默认值 | **生产必须注入** |
| `LIBRARY_BCRYPT_ROUNDS` | `12` | 仅测试调低以加速 |

---

## 6. 测试方式

```bash
cd backend

# 全量测试
uv run pytest -q

# 仅领域层单元测试（不连数据库）
uv run pytest tests/unit -q

# 分层与架构约束校验
uv run pytest tests/integration/test_layering.py -q

# 查看详细输出
uv run pytest -v
```

**测试分层**：

- `tests/unit/` —— 领域层，**不依赖数据库与 Web 框架**（有测试守护这条约束）
- `tests/integration/` —— API 端到端，使用独立内存 SQLite 库，测试之间互不影响

**当前状态**：**376 passed**，连续两次运行结果一致。

---

## 7. 核心用例与接口

### 7.1 核心用例

| 用例 | 说明 | 关键规则 |
|---|---|---|
| UC-201 办理借阅证 | 系统管理员为读者办证 | 一人一证；`CANCELLED` 不计入 |
| UC-101 办理借书 | 图书管理员代理读者借书 | 六项校验固定顺序；失败全部回滚 |
| UC-102 办理还书 | 仅凭馆藏条码归还 | 超期生成罚款；触发预约预留 |
| UC-102a 计算超期罚款 | 还书时触发（include 用例） | 宽限 2 天、单笔封顶 100 元 |
| UC-005 预约图书 | 读者预约全部副本不可借的题录 | 队列上限 5 人；按创建时间排队 |
| UC-006 取消预约 | `ACTIVE` 与 `READY` 均可取消 | 副本转交下一位，保持 `RESERVED` |
| UC-007 续借图书 | 读者自助续借 | 最多 2 次、每次 +7 天；**有预约也可续借** |
| UC-004 查询借阅信息 | 读者查本人 / 馆员查任意读者 | 在借、历史、超期、预约、罚款五段 |
| UC-208/210 书目与馆藏 | 题录与副本的增删 | ISBN 部分唯一；条码全局唯一 |
| UC-213/214 规则维护 | 在线修改借阅与罚款规则 | 立即生效于新业务，**不追溯**已有记录 |

### 7.2 主要接口

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/auth/register` | 公开 | 读者注册 |
| POST | `/api/auth/login` | 公开 | 登录（返回 24h JWT） |
| POST | `/api/admin/borrow-cards` | 系统管理员 | 办理借阅证 |
| POST | `/api/admin/borrow-cards/{id}/{cancel\|restore\|suspend\|resume}` | 系统管理员 | 借阅证状态流转 |
| GET | `/api/books` | 公开 | 查询图书（关键词 / 类型 / 仅可借，分页） |
| POST | `/api/admin/book-titles` | 系统管理员 | 添加题录 |
| POST | `/api/admin/library-items` | 系统管理员 | 添加馆藏副本 |
| POST | `/api/circulation/precheck` | 馆员 | 借书前置校验（只读） |
| POST | `/api/circulation/borrow` | 馆员 | 办理借书 |
| POST | `/api/circulation/return` | 馆员 | 办理还书 |
| POST | `/api/circulation/loans/{id}/renew` | 本人或馆员 | 续借 |
| POST | `/api/fines/{id}/collect` | 馆员 | 收缴罚款 |
| POST | `/api/reservations` | 读者 | 预约图书 |
| DELETE | `/api/reservations/{id}` | 本人 | 取消预约 |
| GET | `/api/me/loans` \| `/api/me/fines` \| `/api/me/reservations` | 读者 | 查询本人数据 |
| GET | `/api/readers/{id}/loans` | 馆员 | 查询指定读者借阅信息 |
| GET / PUT | `/api/policies` \| `/api/admin/policies/{borrow\|fine}` | 登录 / 系统管理员 | 规则查询与维护 |
| GET | `/api/admin/collection-stats` | 系统管理员 | 馆藏统计 |

**完整定义（请求参数、响应、权限、成功与失败场景）见 `specs/14-api-spec.md`。**

### 7.3 快速体验（curl）

```bash
# 1. 登录管理员
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<你的密码>","role":"SYSTEM_ADMIN"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. 读者注册
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"reader001","password":"reader123","name":"张三","department":"计算机学院","reader_type":"UNDERGRADUATE"}'

# 3. 办借阅证
curl -s -X POST http://127.0.0.1:8000/api/admin/borrow-cards \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"reader_id":1}'
```

---

## 8. UML 文档说明

本项目的 UML 统一采用 **Mermaid**（`constitution.md` 第三条），以文本形式内嵌在 Markdown 中，可直接在 Git 中 diff 与评审（实验文档建议的 PlantUML `.puml` 已按同一要求改写，扩展名相应改为 `.md`）。

| 文档 | 内容 | 图数 |
|---|---|---|
| `03-use-cases.md` | 用例一览图 | 1 |
| `04-use-case-model.md` | 用例图与关系说明 | 5 |
| `06-domain-class-diagram.md` | 领域类图（继承、聚合、依赖、状态机） | 7 |
| `08-package-diagram.md` | 包图与依赖规则 | 7 |
| `10-sequence-borrow-book.md` | 办理借书顺序图（含 6 个异常分支） | 1 |
| `11-sequence-return-book.md` | 办理还书顺序图（含罚款计算链） | 1 |
| `12-sequence-reserve-book.md` | 预约图书顺序图（含排队与交接） | 1 |
| `13-database-design.md` | ER 图 | 1 |

合计 **24 张**。

---

## 9. Agent 使用说明

本项目采用 **Spec-Driven + Agent 辅助**范式，完整过程留痕在两份文档中：

| 文档 | 用途 |
|---|---|
| `specs/19-ai-usage-log.md` | **实验要求的正式交付物**：逐次记录使用工具、阶段、任务、输入 Prompt 摘要、Agent 修改文件、输出摘要、测试结果、人工审查结果、Git 提交 |
| `worklog.md` | Agent 行为的**时序**记录，用于过程留痕与答辩说明"谁做了什么" |

**人机分工**：

| 角色 | 职责 |
|---|---|
| Agent | 起草规格、生成设计、实现代码、编写测试、自检并报告问题 |
| 人工 | 拍板决策点、审查规格与代码 diff、冻结 baseline、发现 Agent 的越界 |

**已确立的交互约定**：

- Git 由**用户主导**，Agent 只推荐 commit message；用户明确说「允许执行」才提交
- commit message 格式：**英文标头 + 中文描述**
- 规格冻结后**实现阶段不得修改 `specs/`**；发现规格问题须先报告，由人工决定是否修订并重新冻结

**实现阶段由 Agent 发现并报告的规格问题共 7 项**（含 1 处真实分层违规、1 处外键缺陷），详见 `specs/16-tasks.md` 附录 C。

---

## 10. 已知限制与取舍

| 项 | 说明 |
|---|---|
| 无前端 | 实验二不含前端环节；`frontend/` 为空，包管理约定为 pnpm |
| 无并发控制 | 依赖 SQLite 写串行化，未引入乐观锁（ADR-03）；换 PostgreSQL 时需补 `version` 列 |
| 无独立审计表 | 操作人记录在各业务表字段中（ADR-04）；系统管理员代行流通时 `loans.librarian_id` 为 `NULL` |
| 罚款为线下收缴 | 系统不接入在线支付，只做状态标记（BR-031） |
| 无自助找回密码 | 前端提示"请联系管理员重置"，由管理员重置（Q-05 裁定） |
| 预约失效为惰性判定 | 不引入定时任务，在查询/还书时判定（Q-01 裁定） |
| `LIBRARY_JWT_SECRET` 有开发默认值 | 生产部署必须通过环境变量注入 |
