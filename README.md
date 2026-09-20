# AI时代图书管理系统

> 《软件设计与体系结构》课程实验 —— 图书管理系统的规格驱动（Spec-Driven）实现。
>
> 实验一交付需求、用例、领域模型、架构与数据库设计规格；**实验二**交付详细设计、接口规范、测试设计与后端实现。

---

## 1. 项目简介

一个面向高校图书馆的**借阅流通管理系统**，覆盖读者管理、借阅证管理、书目与馆藏管理、借还流通、预约排队、超期罚款、规则维护与统计。

系统以 **Agent 辅助 + 人工审查**的方式开发：规格（`specs/`）由 Agent 起草、人工拍板并冻结，代码严格按规格实现，架构约束（分层、依赖方向、规则不硬编码）由**自动化测试**守护。

**范围说明**：实验二验收标准以「借书、还书、预约、查询至少可用」+ 自动化测试通过为准，其正式交付为**后端 REST API**（`backend/`）。在此基础上，本项目**额外配套实现了一套可用的 Web 前端**（`frontend/`），用于直观演示与端到端联调，不改变实验二的验收口径。

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
| **前端框架** | **React + TypeScript + Vite** | 18.3 / 5.6 / 5.4 |
| **前端路由** | **React Router** | 6.x |
| **前端包管理** | **pnpm** | ≥ 9 |

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
│   ├── pyproject.toml           # 依赖清单 + pytest/ruff 配置（uv）
│   ├── uv.lock                  # 锁文件（提交 Git）
│   └── .python-version          # 3.14
├── frontend/                    # 前端（实验二范围外，另行实现的演示用 Web 客户端）
│   ├── src/
│   │   ├── api/                 # 类型镜像 + 请求客户端 + 端点封装
│   │   │   ├── types.ts         # 与后端 DTO 一一对应的 TS 类型 + 枚举字典
│   │   │   ├── client.ts        # fetch 封装、错误归一化、401 全局登出、令牌持久化
│   │   │   └── endpoints.ts     # 按 router 分组的 API 函数
│   │   ├── auth/                # 认证上下文与路由守卫
│   │   ├── components/          # 设计系统组件（UI 原语、图标、Toast）
│   │   ├── layouts/             # 应用骨架（侧边栏按角色过滤 + 顶栏）
│   │   ├── pages/               # 页面：reader / staff / admin 三组
│   │   ├── styles/              # 设计 token、组件样式、布局、登录页样式
│   │   └── utils/               # 时间与金额格式化
│   ├── vite.config.ts           # dev proxy：/api → http://127.0.0.1:8000
│   ├── pnpm-workspace.yaml      # onlyBuiltDependencies 白名单
│   └── package.json
├── .vscode/                     # VS Code 配置（解释器、测试发现、推荐扩展）
├── pytest.ini                   # 根目录 pytest 入口（使仓库根可直接跑测试）
├── run-tests.ps1                # 一键测试脚本（自动定位环境 / 回退）
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
uv run python scripts/init_db.py --admin-username admin --admin-name "系统管理员" --admin-password <你的密码>
```

初始化脚本**幂等**：重复执行只补齐缺失行（已存在的规则和管理员自动跳过），可安全重跑。

> **Windows 用户注意**：脚本输出刻意使用 ASCII（`[OK]` / `[SKIP]` / `[FAIL]`）。
> Windows 控制台默认 GBK 编码，打印 `✓` 这类符号会直接抛 `UnicodeEncodeError`
> 中断脚本（此时表可能已建好，但初始化未完成）。

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

### 5.5 Windows 一键启动（PowerShell）

```powershell
cd backend
uv sync                                                              # 首次
uv run python scripts/init_db.py --admin-username admin --admin-password Admin@12345
uv run uvicorn app.main:app --reload --port 8000
```

浏览器直接打开 http://127.0.0.1:8000/docs 就能在 **Swagger UI** 里点着试各个接口。

### 5.6 启动前端（Web 界面）

前端**不是实验二的验收项**，但已完整实现并可直接使用。

```powershell
cd frontend
pnpm install          # 首次
pnpm dev              # 启动开发服务器（默认 http://127.0.0.1:5173）
```

**用法要点**：

| 项 | 说明 |
|---|---|
| 访问地址 | http://127.0.0.1:5173 （若用 `localhost` 亦可，二者指向同一服务） |
| 接口代理 | Vite 已把 `/api` 代理到 `http://127.0.0.1:8000`，**需先启动后端** |
| 登录身份 | 登录页左上可选「读者 / 图书管理员 / 系统管理员」，会随请求带上对应 `role` |
| 账号来源 | 系统管理员账号由 `init_db.py` 创建；馆员账号由系统管理员在「账号管理」中添加；读者可自助注册（注册后须办证才能借书） |
| 其他命令 | `pnpm typecheck`（类型检查）、`pnpm build`（生产构建）、`pnpm preview`（预览构建产物） |

**打开顺序**：先起后端（5.3），再起前端（本节），否则列表与登录会因代理目标不可达而失败。

**页面一览**：

| 角色 | 页面 | 能力 |
|---|---|---|
| 读者 | 图书检索 | 关键词 / 类型 / 仅看可借筛选、分页、无可借副本时预约 |
| 读者 | 我的借阅 | 当前在借 / 历史记录 / 我的预约 / 罚款记录，自助续借、取消预约 |
| 馆员 | 借还流通 | 借书前置校验（六项明细）+ 确认弹窗；凭条码还书 |
| 馆员 | 读者查询 | 按读者编号查在借 / 超期 / 历史 / 预约 / 罚款 |
| 馆员 | 罚款收缴 | 查询读者罚款、标记已缴 |
| 管理员 | 借阅证管理 | 办证、按读者查证、挂失 / 解挂 / 注销 / 恢复 |
| 管理员 | 书目与馆藏 | 题录增删、新增副本、副本状态标记 |
| 管理员 | 规则维护 | 借阅规则与罚款规则在线编辑 |
| 管理员 | 账号管理 | 馆员账号增删、重置密码 |
| 管理员 | 馆藏统计 | 题录 / 副本总量、按状态与类型分布 |

---

## 5b. 端到端联调记录

前端实现完成后，已对**真实后端**跑通完整业务链路（经由 Vite 代理，即前端实际走的路径）：

| 链路 | 验证内容 | 结果 |
|---|---|---|
| 认证 | 三类角色登录、读者注册、`/auth/me` | 通过 |
| 权限 | 读者访问管理员端点 → 403 | 通过 |
| 书目 | 建题录、加副本（条码自动生成） | 通过 |
| 办证 | 办证 / 挂失 / 解挂 / 注销 / 恢复（按 `card_id`） | 通过 |
| 借书 | 前置校验 → 借出 → 库存 -1 → 借阅记录生成（30 天） | 通过 |
| 续借 | 读者自助续借，`renew_count` +1 | 通过 |
| 预约 | 无可借副本时预约成功，返回排队序号与 7 天有效期 | 通过 |
| 还书 | 凭条码归还、超期天数与罚款计算、副本状态回落 | 通过 |
| 查询 | `/me/loans` 五段结构、`/me/fines`、馆员查读者 | 通过 |
| 规则 | `borrow_policies` 5 条 + `fine_rules` 5 条 | 通过 |
| 统计 | 馆藏统计、公开检索 | 通过 |
| 边界 | 非法卡号格式 → 422、错误密码 → 401、无令牌 → 401、非法 ISBN → 400 | 通过 |

浏览器实测（真实 Chromium）走通了「管理员登录 → 馆员借书 → 馆员还书 → 读者查我的借阅」全程，界面截图存于 `.workbuddy/shots/`。

---

## 6. 测试方式

pytest 已随 `uv sync` 装进虚拟环境（**pytest 9.1.1**，位于 `backend/.venv`），**无需额外安装**。

### 6.1 三种运行入口

| 入口 | 命令 | 说明 |
|---|---|---|
| 一键脚本（推荐） | `.\run-tests.ps1` | 自动定位环境；无环境时自动 `uv sync`；机器上没有 uv 会回退到 venv 的 python |
| 仓库根目录 | `uv run --project backend pytest -q` | 根目录 `pytest.ini` 已把 `backend/` 加入 `sys.path` |
| backend 目录 | `cd backend` → `uv run pytest -q` | 用 `backend/pyproject.toml` 里的 pytest 配置 |

> **为什么需要根目录的 `pytest.ini`**：pytest 只从当前目录**向上**找配置文件，不会向下找。
> 在仓库根目录直接运行时会找不到 `backend/pyproject.toml`，于是 `import app` 报
> `ModuleNotFoundError`。根目录这份配置只负责「找到测试」+「让 `app` 可导入」，
> 其余配置的唯一来源仍是 `backend/pyproject.toml`。

**不用 uv 也可以**（虚拟环境已建好的前提下）：

```powershell
# 方式一：直接调 venv 里的 pytest（无需激活）
.\backend\.venv\Scripts\pytest.exe -q

# 方式二：激活虚拟环境后用裸命令
cd backend
.\.venv\Scripts\Activate.ps1      # PowerShell
pytest -q
```

### 6.2 一键脚本用法

```powershell
.\run-tests.ps1                              # 全部测试
.\run-tests.ps1 -Scope unit                  # 仅领域层单元测试
.\run-tests.ps1 -Scope integration           # 仅 API 端到端测试
.\run-tests.ps1 -Scope layering              # 仅架构约束校验
.\run-tests.ps1 -Scope unit -Keyword money   # 按名称筛选（等价 pytest -k）
.\run-tests.ps1 -NoUv                        # 强制不用 uv
```

> 脚本刻意**只用 ASCII 输出**：Windows PowerShell 5.1 在中文系统上按 GBK 解析 `.ps1`，
> 无 BOM 的 UTF-8 中文字符串会乱码，甚至破坏字符串终止符导致脚本无法解析。

### 6.3 常用 pytest 用法

```bash
# 单个文件
uv run pytest tests/integration/test_borrow.py -q

# 单个类 / 单个用例
uv run pytest tests/integration/test_borrow.py::TestBorrowFailures -q
uv run pytest "tests/integration/test_return.py::TestFineGeneration::test_overdue_return_creates_fine" -q

# 按关键字筛（大小写不敏感，支持 and/or/not）
uv run pytest -k "fine and not collect" -q

# 失败即停 + 打印完整局部变量
uv run pytest -x -l

# 只重跑上次失败的用例
uv run pytest --lf

# 显示最慢的 10 个用例
uv run pytest --durations=10
```

### 6.4 IDE 配置

**VS Code** —— 已被 `.vscode/settings.json` 预配置好，**开箱即用**：

- 解释器指向 `backend/.venv/Scripts/python.exe`
- 测试面板（左侧试管图标）自动发现全部用例，可单点运行 / 调试
- Pylance 通过 `python.analysis.extraPaths` 解析 `app.*` 与 `scripts.*`
- 推荐扩展列在 `.vscode/extensions.json`（Python / Pylance / Ruff）

**PyCharm** —— 手动指定一次：

1. `Settings → Project → Python Interpreter → Add Local Interpreter`
2. 选 `Existing`，路径填 `backend\.venv\Scripts\python.exe`
3. `Settings → Tools → Python Integrated Tools → Testing → Default test runner` 选 `pytest`
4. 右键 `backend/tests` → `Run 'pytest in tests'`

### 6.5 测试分层

- `tests/unit/` —— 领域层，**不依赖数据库与 Web 框架**（这条约束本身也有测试守护）
- `tests/integration/` —— API 端到端，每个用例使用独立内存 SQLite 库，互不影响
- `tests/integration/test_layering.py` —— 架构约束校验：用 `ast` 解析真实 import 语句，
  检查分层依赖方向（R-1/R-2/R-3/D-7）、规则数值未硬编码、表数 = 11、部分唯一索引存在

### 6.6 当前状态

**376 passed**，连续两次运行结果一致（约 21 ~ 35 s，视冷/热启动而定）。
首次运行偏慢是因为 bcrypt 与 SQLite 的冷启动；测试内已通过 `LIBRARY_BCRYPT_ROUNDS=4` 降低哈希成本。

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
| 前端不在实验二验收范围 | `frontend/` 是配套实现的演示客户端，实验二的正式交付物仍为后端 API 与自动化测试 |
| 前端未覆盖的接口 | 「查询全部借阅证列表」后端未暴露 HTTP 端点（仓储层有 `find_parent` 能力但规格未定义该接口），前端改为按读者查询；界面已如实标注 |
| 无并发控制 | 依赖 SQLite 写串行化，未引入乐观锁（ADR-03）；换 PostgreSQL 时需补 `version` 列 |
| 无独立审计表 | 操作人记录在各业务表字段中（ADR-04）；系统管理员代行流通时 `loans.librarian_id` 为 `NULL` |
| 罚款为线下收缴 | 系统不接入在线支付，只做状态标记（BR-031） |
| 无自助找回密码 | 前端提示"请联系管理员重置"，由管理员重置（Q-05 裁定） |
| 预约失效为惰性判定 | 不引入定时任务，在查询/还书时判定（Q-01 裁定） |
| `LIBRARY_JWT_SECRET` 有开发默认值 | 生产部署必须通过环境变量注入 |
