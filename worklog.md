# Worklog — AI时代图书管理系统实验

> 本文件按时间顺序记录 AI Agent 在本项目中执行的每一步操作。
> 每步格式：日期 / 阶段 / 做了什么 / 产出文件 / 状态。
> 详细内容另见 `specs/19-ai-usage-log.md`（实验要求的 AI 使用记录）。

---

## 2026-09-19

### 步骤 0：阅读实验文档，确认项目规划

**阶段**：准备

**操作**：
1. 阅读 `docs_expr_description/` 下全部 4 份实验文档（实验概述、实验一、实验二、Agent提示词手册）。
2. 与用户确认关键决策：
   - 技术栈：Python + FastAPI（后端），TypeScript（前端，允许使用 React）
   - 目录结构：根目录下 `specs/`、`frontend/`、`backend/`
   - 规格文档语言：中文
   - Git：由用户主导，Agent 仅推荐 commit message，用户要求时才执行
   - 澄清问题：Agent 先给方案，用户逐条审查
   - 规则数值：实验文档已给的部分直接采用，未给的部分由用户定义
3. 目录整理：删除空目录 `docs/`，新建 `specs/`、`frontend/`、`backend/`。

**产出**：`specs/`、`frontend/`、`backend/`（目录）、本文件

**状态**：完成

---

### 步骤 1：编写 Project Brief

**阶段**：实验一 / 初始阶段 Inception

**操作**：
1. 依据实验文档第五节的模板，结合已确认的技术栈和目录结构，编写 `specs/00-project-brief.md`。
2. 补充了原模板未涵盖的内容：可运行交付物要求、前后端职责边界、规格文档语言约定。

**产出**：`specs/00-project-brief.md`（新建）

**待用户确认**：Project Brief 内容

**状态**：待审查

---
