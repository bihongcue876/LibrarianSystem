# AI时代图书管理系统

> 《软件设计与体系结构》课程实验 —— 图书管理系统的规格驱动（Spec-Driven）实现。
>
> 实验一交付需求、用例、领域模型、架构与数据库设计规格；**实验二**交付详细设计、接口规范、测试设计与后端实现。

---

## 1. 这是什么

一个面向高校图书馆的**借阅流通管理系统**，覆盖读者管理、借阅证管理、书目与馆藏管理、借还流通、预约排队、超期罚款、规则维护与统计。

系统以 **Agent 辅助 + 人工审查**的方式开发：规格（`specs/`）由 Agent 起草、人工拍板并冻结，代码严格按规格实现，架构约束（分层、依赖方向、规则不硬编码）由**自动化测试**守护。

**交付范围**：实验二验收标准以「借书、还书、预约、查询至少可用」+ 自动化测试通过为准，其正式交付物为**后端 REST API**（`backend/`，376 个用例全绿）。在此基础上额外配套实现了一套可用的 **Web 前端**（`frontend/`），用于直观演示与端到端联调，不改变实验二的验收口径。

---

## 2. 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 语言 | Python | **3.14** |
| Web 框架 | FastAPI | ≥ 0.115 |
| 数据校验 / DTO | Pydantic | ≥ 2.x |
| ORM | SQLAlchemy | ≥ 2.x |
| 数据库 | SQLite | 内置 |
| 密码哈希 / 令牌 | bcrypt / PyJWT | ≥ 4.1 / ≥ 2.8 |
| 测试 | pytest + httpx | ≥ 8.x |
| **后端依赖管理** | **uv** | ≥ 0.5 |
| **前端** | **React + TypeScript + Vite + React Router** | 18.3 / 5.6 / 5.4 / 6.x |
| **前端包管理** | **pnpm** | ≥ 9 |

`pyproject.toml` + `uv.lock` 是后端依赖的唯一来源，**不使用 `requirements.txt`**。

---

## 3. 目录结构

```
expr_proj/
├── specs/          规格文档（实验一 00~08 + 实验二 09~19 + constitution）
├── backend/        FastAPI 后端（分层架构：presentation / application / domain / infrastructure）
├── frontend/       React 前端（演示客户端，非实验二验收项）
├── pytest.ini      仓库根 pytest 入口
├── run-tests.ps1   一键测试脚本
├── worklog.md      Agent 行为时序记录
├── DEVELOPMENT.md  使用与开发手册（详细）
└── README.md
```

---

## 4. 启动方式

### 4.1 后端

```powershell
cd backend
uv sync                                                                          # 首次：安装 Python 3.14 并同步依赖
uv run python scripts/init_db.py --admin-username admin --admin-password <密码>   # 首次：建表 + 播种规则 + 创建管理员
uv run python scripts/seed_catalog.py                                           # 可选：播种默认书目（题录 + 馆藏副本）
uv run uvicorn app.main:app --reload --port 8000                                # 启动
```

| 入口 | 地址 |
|---|---|
| 服务 | http://127.0.0.1:8000 |
| 交互式 API 文档（Swagger UI） | http://127.0.0.1:8000/docs |
| OpenAPI 契约 | http://127.0.0.1:8000/openapi.json |
| 健康检查 | http://127.0.0.1:8000/api/health |

> **入口是 `uvicorn`，不是 `python app/main.py`**。`app/main.py` 是 ASGI 应用模块，没有 `__main__` 入口；直接按文件路径运行还会因 `sys.path` 不含 `backend/` 而报 `ModuleNotFoundError: No module named 'app'`。
>
> 初始化脚本**幂等**（重复执行只补齐缺失项），但**不会重置已存在账号的密码**——忘记管理员密码需另行处理。密码必须显式传入，无默认值。

### 4.2 前端

```powershell
cd frontend
pnpm install          # 首次
pnpm dev              # 开发服务器
```

浏览器打开 **http://localhost:5173**。

> ⚠️ 请用 `localhost`，**不要用 `127.0.0.1:5173`**。Vite 默认监听主机名 `localhost`，Node 在本机优先解析为 IPv6 回环 `::1`，因此 `127.0.0.1:5173` 会连接被拒（已实测）。
>
> 前端通过 Vite 代理把 `/api` 转发到 `http://127.0.0.1:8000`，**必须先启动后端**。

### 4.3 测试

```powershell
.\run-tests.ps1                              # 全部用例
.\run-tests.ps1 -Scope unit -Keyword money   # 按范围 / 关键字筛选
```

当前状态：**376 passed**（约 13 秒）。

---

## 5. 更多文档

| 文档 | 内容 |
|---|---|
| **`DEVELOPMENT.md`** | 环境准备、环境变量、测试入口详解、架构与分层约束、接口清单、UML 说明、端到端联调记录、已知限制 |
| `specs/` | 实验一 / 二的规格文档（需求、用例、领域模型、架构、详细设计、API 规范、测试计划、AI 使用记录等） |
| `specs/14-api-spec.md` | **接口权威定义**（请求参数、响应、权限、成功与失败场景） |
| `worklog.md` | Agent 行为时序记录 |
| `specs/19-ai-usage-log.md` | 实验要求的正式交付物：逐次 AI 使用记录 |
