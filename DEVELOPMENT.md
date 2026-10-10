# 使用与开发手册（DEVELOPMENT.md）

> 本文承接 `README.md` 的详细内容：环境准备、测试入口、架构约束、接口清单、联调记录与已知限制。
> 接口的**权威定义**始终是 `specs/14-api-spec.md`；本文与其冲突时以规格为准。

---

## 1. 环境准备

```powershell
# 安装 uv（若未安装）
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

cd backend
uv python install 3.14     # 安装并固定 Python 3.14
uv sync                    # 解析 uv.lock，自动创建 .venv
```

**为什么用 uv**：可直接安装并固定解释器版本（本项目需 3.14）、锁文件覆盖传递依赖、解析安装快。
`pyproject.toml` + `uv.lock` 是唯一依赖来源，**不使用 `requirements.txt`**。

---

## 2. 初始化数据库

```powershell
# 建表 + 播种借阅规则与罚款规则 + 创建首个系统管理员
# 密码必须显式传入，无默认值（初始化密码不硬编码）
uv run python scripts/init_db.py --admin-username admin --admin-name "系统管理员" --admin-password <你的密码>
```

初始化脚本**幂等**：重复执行只补齐缺失行（已存在的规则和管理员打 `[SKIP]`），可安全重跑。

> **Windows 用户注意**：脚本输出刻意使用 ASCII（`[OK]` / `[SKIP]` / `[FAIL]`）。
> Windows 控制台默认 GBK 编码，打印 `✓` 这类符号会直接抛 `UnicodeEncodeError`
> 中断脚本（此时表可能已建好，但初始化未完成）。

初始化脚本会写入：

- 5 条借阅规则（专科/本科 5 册 30 天、研究生 10 册 60 天、博士 15 册 90 天、教师 20 册 90 天）
- 5 条罚款规则（中文书 0.20、外文书 0.50、中文杂志 0.10、外文杂志 0.20、论文 1.00 元/天；宽限 2 天，单笔封顶 100 元）
- 1 个系统管理员账号

**三个已实测确认的细节**：

| 细节 | 说明 |
|---|---|
| 数据库路径是**绝对的** | `session.py` 以自身位置推导 `<backend>/library.db`，与当前工作目录无关；从仓库根调用 `uv run --project backend python backend/scripts/init_db.py ...` 也能落到同一个库 |
| 缺 `--admin-password` 会清晰报错 | argparse `error: the following arguments are required: --admin-password`，exit code 2 |
| **不会重置已存在账号的密码** | 同名管理员直接 `[SKIP]`。忘记密码时重跑初始化**无效**，需改库中 `password_hash` 或换用户名 |

### 2.1 默认书目（可选，独立脚本）

`init_db.py` 只建结构、写规则、建管理员，**不**预置藏书。需要一组默认书目用于演示或联调时，运行独立脚本：

```powershell
uv run python scripts/seed_catalog.py                 # 读 backend/data/default_catalog.json
uv run python scripts/seed_catalog.py --data <路径>   # 指定数据文件
```

- 书目属于**数据**，放在 `backend/data/default_catalog.json`：约 10 个题录，覆盖五种 `item_type`（中/外文图书、中/外文期刊、学位论文）；每个题录预置副本，条码自 `BC00000001` 起，初始状态 `AVAILABLE`。
- 脚本**幂等**：同名活跃题录已存在则跳过；题录下已有副本则不再补。可安全重跑。
- `created_by` 取库中首个系统管理员；若库中尚无管理员则为 NULL（建议先执行 `init_db.py`）。

---

## 3. 启动服务

```powershell
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

- 服务地址：http://127.0.0.1:8000
- 交互式 API 文档（Swagger UI）：http://127.0.0.1:8000/docs
- OpenAPI 契约：http://127.0.0.1:8000/openapi.json
- 健康检查：`GET /api/health`

### 3.1 为什么入口是 `uvicorn`，不是 `python app/main.py`

| 尝试 | 结果 | 原因 |
|---|---|---|
| `uv run app` | `program not found` | `uv run` 后面跟的是**可执行文件/脚本名**，不是包名；`uv run` 空参列出的命令清单属正常输出，不是报错 |
| `uv run python app/main.py` | `ModuleNotFoundError: No module named 'app'` | 直接跑文件时 `sys.path[0]` 变成 `backend/app`，`backend/` 不在导入路径上；且 `main.py` **没有 `if __name__ == "__main__"` 块**，它只是 ASGI 应用模块 |
| `uv run python main.py` | 文件不存在 | `main.py` 在 `app/` 下 |

`scripts/init_db.py` 能直接 `python scripts/init_db.py` 运行，是因为它自己
`sys.path.insert(0, parents[1])`——两个脚本写法不同，不要据此推断 `main.py` 也能这么跑。

### 3.2 Swagger UI 的限制

后端的鉴权守卫是普通 `Depends` 依赖，**未声明 OpenAPI `securitySchemes`**，
因此 `/docs` 页面**没有 Authorize 按钮**，无法在 UI 里填 Bearer token——
只有公开接口（注册、登录、图书检索、健康检查）能在 Swagger UI 里直接点着试。
需要登录的接口请用第 9 节的命令行片段或前端演示。

### 3.3 前端

```powershell
cd frontend
pnpm install          # 首次
pnpm dev              # 开发服务器
pnpm typecheck        # 类型检查
pnpm build            # 生产构建
pnpm preview          # 预览构建产物
```

浏览器打开 **http://localhost:5173**。

> ⚠️ **请用 `localhost`，不要用 `127.0.0.1:5173`**。
> Vite 默认监听主机名 `localhost`，Node 在本机优先将其解析为 IPv6 回环 `::1`，
> 因此 dev server 只绑定了 `[::1]:5173`——`http://127.0.0.1:5173` 会**连接被拒**（已实测）。
> 后端恰好相反：uvicorn 默认只绑定 IPv4 `127.0.0.1:8000`，`[::1]:8000` 不通。
> 想消除这个差别，可在 `vite.config.ts` 里显式设 `server.host: "127.0.0.1"`。

**用法要点**：

| 项 | 说明 |
|---|---|
| 接口代理 | Vite 已把 `/api` 代理到 `http://127.0.0.1:8000`，**需先启动后端** |
| 登录身份 | 登录页左上可选「读者 / 图书管理员 / 系统管理员」，会随请求带上对应 `role` |
| 账号来源 | 系统管理员账号由 `init_db.py` 创建；馆员账号由系统管理员在「账号管理」中添加；读者可自助注册（注册后须办证才能借书） |

**打开顺序**：先起后端（§3），再起前端（本节），否则列表与登录会因代理目标不可达而失败。

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

## 4. 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LIBRARY_DATABASE_URL` | 由 `LIBRARY_DB_PATH` 推导的 `sqlite:///<backend 绝对路径>/library.db` | 数据库连接串，优先级更高 |
| `LIBRARY_DB_PATH` | `<backend>/library.db`（绝对路径，与工作目录无关） | SQLite 文件路径 |
| `LIBRARY_JWT_SECRET` | `dev-secret-change-me-in-production` | **生产必须注入** |
| `LIBRARY_BCRYPT_ROUNDS` | `12` | 仅测试调低以加速 |

四个变量均在代码中真实读取（`db/session.py`、`security/jwt.py`、`security/password.py`）。

---

## 5. 测试方式

pytest 已随 `uv sync` 装进虚拟环境（**pytest 9.1.1**，位于 `backend/.venv`），**无需额外安装**。

### 5.1 四种运行入口（全部实测通过）

| 入口 | 命令 | 说明 |
|---|---|---|
| 一键脚本（推荐） | `.\run-tests.ps1` | 用 `$PSScriptRoot` 定位项目，**与调用目录无关**；缺环境时自动 `uv sync`；机器上没有 uv 会回退到 venv 的 python |
| 仓库根目录 | `uv run --project backend pytest -q` | 根目录 `pytest.ini` 已把 `backend/` 加入 `sys.path` |
| backend 目录 | `cd backend` → `uv run pytest -q` | 用 `backend/pyproject.toml` 里的 pytest 配置 |
| 直接调 venv | `.\backend\.venv\Scripts\pytest.exe -q` | 无需激活虚拟环境，也不经过 uv |

四个入口实测均为 **376 passed**（约 13 秒，warm）。

> **为什么需要根目录的 `pytest.ini`**：pytest 只从当前目录**向上**找配置文件，不会向下找。
> 在仓库根目录直接运行时会找不到 `backend/pyproject.toml`，于是 `import app` 报
> `ModuleNotFoundError`。根目录这份配置只负责「找到测试」+「让 `app` 可导入」，
> 其余配置的唯一来源仍是 `backend/pyproject.toml`。

### 5.2 一键脚本用法

```powershell
.\run-tests.ps1                              # 全部测试
.\run-tests.ps1 -Scope unit                  # 仅领域层单元测试
.\run-tests.ps1 -Scope integration           # 仅 API 端到端测试
.\run-tests.ps1 -Scope layering              # 仅架构约束校验（20 passed）
.\run-tests.ps1 -Scope unit -Keyword money   # 按名称筛选（等价 pytest -k）
.\run-tests.ps1 -NoUv                        # 强制不用 uv
```

> 脚本刻意**只用 ASCII 输出**：Windows PowerShell 5.1 在中文系统上按 GBK 解析 `.ps1`，
> 无 BOM 的 UTF-8 中文字符串会乱码，甚至破坏字符串终止符导致脚本无法解析。

已知小瑕疵：pytest 输出里带中文工作区路径的告警行（如 starlette 弃用提示）在
PowerShell 5.1 控制台会显示为乱码——控制台按 GBK 解码了 Python 的 UTF-8 输出，
属**显示问题**，不影响退出码与测试判定。

### 5.3 常用 pytest 用法

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

### 5.4 IDE 配置

**VS Code** —— 已被 `.vscode/settings.json` 预配置好，**开箱即用**（解释器路径已核对存在）：

- 解释器指向 `backend/.venv/Scripts/python.exe`
- 测试面板（左侧试管图标）自动发现全部用例，可单点运行 / 调试
- Pylance 通过 `python.analysis.extraPaths` 解析 `app.*` 与 `scripts.*`
- 推荐扩展列在 `.vscode/extensions.json`（Python / Pylance / Ruff）

**PyCharm** —— 手动指定一次：

1. `Settings → Project → Python Interpreter → Add Local Interpreter`
2. 选 `Existing`，路径填 `backend\.venv\Scripts\python.exe`
3. `Settings → Tools → Python Integrated Tools → Testing → Default test runner` 选 `pytest`
4. 右键 `backend/tests` → `Run 'pytest in tests'`

### 5.5 测试分层

- `tests/unit/` —— 领域层，**不依赖数据库与 Web 框架**（这条约束本身也有测试守护）
- `tests/integration/` —— API 端到端，每个用例使用独立内存 SQLite 库，互不影响
- `tests/integration/test_layering.py` —— 架构约束校验：用 `ast` 解析真实 import 语句，
  检查分层依赖方向（R-1/R-2/R-3/D-7）、规则数值未硬编码、表数 = 11、部分唯一索引存在

### 5.6 当前状态

**376 passed**，多次运行结果一致（约 **13 s**，warm；冷启动会慢一些）。
测试内已通过 `LIBRARY_BCRYPT_ROUNDS=4` 降低哈希成本。

---

## 6. 架构说明

### 6.1 四层分层

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

### 6.2 分层约束（由测试守护，不靠人工检查）

| 编号 | 约束 | 守护测试 |
|---|---|---|
| R-1 | 路由不得依赖 `infrastructure` | `test_routers_do_not_import_infrastructure` |
| R-2 | 应用层不得依赖 `infrastructure`（`dependencies.py` 是唯一装配点） | `test_application_does_not_import_infrastructure` |
| R-3 | 领域层零框架依赖，只允许标准库与本包 | `test_domain_imports_no_framework_or_outer_layer` |
| D-7 | 实体不得依赖领域服务与工厂 | `test_entities_do_not_depend_on_services_or_factories` |
| BR-049 | 规则数值不得硬编码在代码中 | `test_policies_have_no_rule_literals` |

这些检查用 `ast` 解析**真实的 import 语句**，而非字符串匹配——后者会把 docstring 里对约束的说明误判为违规。

### 6.3 关键设计决策

| 决策 | 理由 |
|---|---|
| 领域实体与 ORM 模型**分离**，用 Mapper 转换 | 领域层不得 `import sqlalchemy`；实体需要行为方法，ORM 模型不该有 |
| 金额列存 **TEXT**（`MoneyType`） | SQLite 无原生 DECIMAL，`Numeric` 会降级为 REAL，重新引入浮点误差（`0.20 × 3 ≠ 0.60`） |
| `loans.status` **只存两态**（`BORROWED` / `RETURNED`） | `OVERDUE` 是派生状态（由 `due_at` 判定），持久化会带来"无人负责的状态陈旧" |
| 规则存库 + **策略对象查表** | `if reader_type == "UNDERGRADUATE": return 5` 这类分支被禁止（BR-049），规则可在线维护 |
| `due_at` / `unit_price` **生成时快照** | 规则修改不追溯已有记录（BR-050），应用层无须额外判断 |
| 事务边界**只在应用服务层** | 事务范围显式可见；Repository 只读写不提交 |
| 三个**部分唯一索引** | 借阅证仅对 `ACTIVE`/`SUSPENDED` 唯一；ISBN 仅对活跃题录唯一（允许已下架书重新采购）；预约仅对有效记录唯一 |

### 6.4 契约速查（写脚本 / 前端前必看）

| 项 | 正确值 |
|---|---|
| 注册读者字段 | `username` / `password` / **`name`** / **`department`**（必填）/ `reader_type` |
| 读者类型枚举 | `COLLEGE` / `UNDERGRADUATE` / `GRADUATE` / **`DOCTOR`** / `TEACHER` |
| 规则响应字段 | **`borrow_policies`** + `fine_rules`（非 `borrow_rules`） |
| 预检明细字段 | `step` / **`ok`** / `code` / `message`（非 `rule`/`passed`） |
| 借阅证操作路径 | `/api/admin/borrow-cards/{card_id}`（**数字主键**）；按卡号查询才用 `{card_no}` |
| ISBN | 必须**校验位正确**（ISBN-10/13），否则 400 `INVALID_ISBN`；不传则跳过 |
| 馆员账号字段 | `username` / `password` / **`name`**（无 `full_name`） |
| 登录必带 `role` | `LoginRequest.role` 默认 `READER`；管理员须传 `"role":"SYSTEM_ADMIN"`，馆员传 `"role":"LIBRARIAN"`，否则拿到的 token 过不了对应守卫（401） |
| API 路径 | **无 `/api/v1` 前缀**，直接 `/api/...` |

---

## 7. 完整目录结构

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
│   ├── scripts/
│   │   ├── init_db.py           # 建表 + 播种规则 + 创建首个系统管理员
│   │   └── seed_catalog.py      # 可选：从 data/ 读取默认书目入库
│   ├── data/
│   │   └── default_catalog.json # 默认书目数据（题录 + 馆藏副本）
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
├── DEVELOPMENT.md               # 本文
└── README.md
```

---

## 8. 接口一览

> 下表由**运行中的 OpenAPI 契约 + 路由源码守卫**自动核对生成（2026-09-20，共 36 条路由）。
> 权限列来自代码守卫：`AdminAccount`＝系统管理员、`StaffAccount`＝图书管理员、
> `ReaderAccount`＝读者、`CurrentAccount`＝任一登录账号。业务级细则（如"仅本人"）见 `specs/14-api-spec.md`。

### 8.1 认证与健康

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/health` | 公开 | 健康检查 |
| POST | `/api/auth/register` | 公开 | 读者注册 |
| POST | `/api/auth/login` | 公开 | 登录（返回 24h JWT，须带 `role`） |
| GET | `/api/auth/me` | 登录 | 当前登录账号信息 |

### 8.2 借阅证（UC-201~205）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/admin/borrow-cards` | 系统管理员 | 办理借阅证（卡号自动生成） |
| POST | `/api/admin/borrow-cards/{card_id}/cancel` | 系统管理员 | 注销 |
| POST | `/api/admin/borrow-cards/{card_id}/restore` | 系统管理员 | 恢复已注销 |
| POST | `/api/admin/borrow-cards/{card_id}/suspend` | 系统管理员 | 挂失 |
| POST | `/api/admin/borrow-cards/{card_id}/resume` | 系统管理员 | 解挂 |
| GET | `/api/borrow-cards/{card_no}` | 登录 | 按卡号查询借阅证信息 |
| GET | `/api/admin/readers/{reader_id}/borrow-cards` | 系统管理员 | 按读者查全部借阅证（含历史注销） |

### 8.3 书目与馆藏（UC-208~212）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/books` | 公开 | 图书检索（关键词 / 类型 / 仅可借，分页） |
| POST | `/api/admin/book-titles` | 系统管理员 | 添加题录 |
| DELETE | `/api/admin/book-titles/{title_id}` | 系统管理员 | 删除题录（软删除） |
| POST | `/api/admin/library-items` | 系统管理员 | 添加馆藏副本 |
| DELETE | `/api/admin/library-items/{item_id}` | 系统管理员 | 删除副本（软删除） |
| POST | `/api/admin/library-items/{item_id}/status` | 系统管理员 | 标记副本状态 |

### 8.4 流通（UC-101/102/006/007）与罚款

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/circulation/precheck` | 图书管理员 | 借书前置校验（只读，六项明细） |
| POST | `/api/circulation/borrow` | 图书管理员 | 办理借书 |
| POST | `/api/circulation/return` | 图书管理员 | 办理还书（凭条码） |
| POST | `/api/circulation/loans/{loan_id}/renew` | 本人或图书管理员 | 续借 |
| POST | `/api/fines/{fine_id}/collect` | 图书管理员 | 收缴罚款 |

### 8.5 预约（UC-005/006）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/reservations` | 读者 | 预约图书 |
| DELETE | `/api/reservations/{reservation_id}` | 读者（本人） | 取消预约 |
| GET | `/api/me/reservations` | 读者 | 我的预约 |

### 8.6 查询

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/me/loans` | 读者 | 我的在借 / 历史 / 超期五段结构 |
| GET | `/api/me/fines` | 读者 | 我的罚款记录 |
| GET | `/api/readers/{reader_id}/loans` | 图书管理员 | 查询指定读者借阅信息 |
| GET | `/api/admin/collection-stats` | 系统管理员 | 馆藏统计 |

### 8.7 规则与账号

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/policies` | 登录 | 查询借阅与罚款规则 |
| PUT | `/api/admin/policies/borrow` | 系统管理员 | 修改借阅规则 |
| PUT | `/api/admin/policies/fine` | 系统管理员 | 修改罚款规则 |
| POST | `/api/admin/librarians` | 系统管理员 | 新增馆员账号 |
| GET | `/api/admin/librarians` | 系统管理员 | 馆员账号列表 |
| DELETE | `/api/admin/librarians/{librarian_id}` | 系统管理员 | 删除馆员账号 |
| POST | `/api/admin/accounts/{account_id}/reset-password` | 系统管理员 | 重置账号密码 |

---

## 9. 快速体验（curl）

### 9.1 Git Bash / WSL / Linux / macOS

```bash
# 1. 登录管理员（注意必须带 role）
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

> ⚠️ 这段是 **bash 语法**。在 PowerShell 里 `$(...)` 不生效，且 `curl` 是
> `Invoke-WebRequest` 的**别名**（参数不兼容），请改用下一小节。

### 9.2 Windows PowerShell 5.1 原生写法

```powershell
# 1. 登录管理员
$resp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/auth/login" `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"username":"admin","password":"<你的密码>","role":"SYSTEM_ADMIN"}'
$token = $resp.access_token

# 2. 读者注册
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/auth/register" `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"username":"reader001","password":"reader123","name":"张三","department":"计算机学院","reader_type":"UNDERGRADUATE"}'

# 3. 办借阅证
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/admin/borrow-cards" `
  -ContentType "application/json; charset=utf-8" `
  -Headers @{ Authorization = "Bearer $token" } `
  -Body '{"reader_id":1}'
```

> 中文 JSON 体在 PowerShell 5.1 下建议用 UTF-8 写入临时文件再 `-InFile` 传入，
> 避免 GBK 控制台编码问题；上面的中文仅作示意。

---

## 10. UML 文档说明

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

上表合计 **24 张**；`18-review-checklist.md` 内另有 1 张检查流程图，全仓库 mermaid 块实数 **25 个**。

---

## 11. 端到端联调记录

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

## 12. Agent 使用说明

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

## 13. 已知限制与取舍

| 项 | 说明 |
|---|---|
| 前端不在实验二验收范围 | `frontend/` 是配套实现的演示客户端，实验二的正式交付物仍为后端 API 与自动化测试 |
| 前端未覆盖的接口 | 「查询全部借阅证列表」后端未暴露 HTTP 端点（仓储层有 `find_parent` 能力但规格未定义该接口），前端改为按读者查询；界面已如实标注 |
| 无并发控制 | 依赖 SQLite 写串行化，未引入乐观锁（ADR-03）；换 PostgreSQL 时需补 `version` 列 |
| 无独立审计表 | 操作人记录在各业务表字段中（ADR-04）；系统管理员代行流通时 `loans.librarian_id` 为 `NULL` |
| 罚款为线下收缴 | 系统不接入在线支付，只做状态标记（BR-031） |
| 无自助找回密码 | 前端提示"请联系管理员重置"，由管理员重置（Q-05 裁定）；`init_db.py` 也不会重置已存在账号的密码 |
| 预约失效为惰性判定 | 不引入定时任务，在查询/还书时判定（Q-01 裁定） |
| `LIBRARY_JWT_SECRET` 有开发默认值 | 生产部署必须通过环境变量注入 |
| Swagger UI 无 Authorize 按钮 | 鉴权走普通 `Depends`，未声明 `securitySchemes`（见 §3.2）；需登录的接口在 UI 里无法直接试 |

---

## 14. 文档自检记录（2026-09-20）

本文档改写前，对 README 中**全部可复制命令与关键断言**做了实机核对。方法：逐条执行 / 用 AST 与运行时自省交叉验证。

### 通过项

| 检查项 | 结果 |
|---|---|
| `init_db.py` 三种调用方式 + 幂等 + 缺参报错 | 通过 |
| 四个 pytest 入口（一键脚本 3 分支、仓库根、backend 目录、venv 直调） | 全部 376 passed |
| 前端 `pnpm install / typecheck / build` | 通过（58 modules，gzip 78.26 kB） |
| 前后端真实联调（Vite 代理 → 后端） | health / books / login 全通 |
| 四个环境变量均被代码读取，默认值与文档一致 | 通过 |
| `.vscode` 解释器路径存在、pytest 9.1.1、Python 3.14.4 | 通过 |
| specs 21 个文件（00~19 + constitution） | 通过 |

### 发现并已修正的不一致

| # | 原文 | 事实 | 处理 |
|---|---|---|---|
| 1 | 前端「访问地址 http://127.0.0.1:5173（若用 localhost 亦可）」 | **说反了**：Vite 只绑 `::1`，`127.0.0.1:5173` 连接被拒，仅 `localhost` 可用 | 改为 localhost 并注明原因 |
| 2 | §7.3 curl 片段未标注 shell | PowerShell 5.1 中 `curl` 是 `Invoke-WebRequest` 别名、`$(...)` 不生效，照抄必错 | 标注 bash 专用并补 PowerShell 版 |
| 3 | 接口表仅列 20 余条、路径参数写 `{id}` | 实际 36 条路由；真实参数名是 `{loan_id}` / `{fine_id}` / `{reader_id}` / `{reservation_id}` | §8 给出全表并改用真实参数名 |
| 4 | 测试「约 21 ~ 35 s」 | 实测 warm 约 13 s | 更新为实测值 |
| 5 | UML「合计 24 张」 | 列表内 24 张无误，但全仓库 mermaid 块为 25（`18-review-checklist.md` 另有 1 张） | 注明口径 |

### 遗留的可选改进（未动代码）

- `vite.config.ts` 显式 `server.host: "127.0.0.1"`，让 `127.0.0.1` 与 `localhost` 都能访问
- 后端声明 OpenAPI `securitySchemes`（如 `HTTPBearer`），让 Swagger UI 出现 Authorize 按钮
- `run-tests.ps1` 在调用 pytest 前临时把 `[Console]::OutputEncoding` 设为 UTF-8，消除告警行中文乱码
- 缺一个「重置管理员密码」脚本：忘记密码时目前只能改库
