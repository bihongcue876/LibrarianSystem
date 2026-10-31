# UML 图格式说明（与教师总述的对应关系）

> 本文件说明本项目 UML 交付物的**实际格式**与教师《实验概述》§6、实验二“步骤 2–4”中 `.puml` 字样的对应关系，避免验收时被误判为“缺图”。

## 1. 实际采用的格式

本项目全部 UML 图以 **Mermaid** 代码块嵌入对应的 `.md` 规格文件，而不是独立的 `.puml` 文件。依据：

1. 《AI 时代软件设计实验工具链说明书》§3.3 推荐 Mermaid（VS Code 插件即可预览，无需安装 Graphviz/PlantUML）。
2. `specs/constitution.md` v1.1 第一条：UML 以 Mermaid 嵌入 `.md`，保证在 GitHub/VS Code 中可直接渲染。
3. 本机没有 PlantUML 渲染环境；若强行输出 `.puml`，反而无法在提交环境中预览。

## 2. 文件对应表

| 教师总述中的文件名 | 本项目实际文件 | 图数 | 类型 |
|---|---|---:|---|
| `04-use-case-model.puml` | `specs/04-use-case-model.md` | 5 | 用例图 |
| `06-domain-class-diagram.puml` | `specs/06-domain-class-diagram.md` | 7 | 类图 |
| `08-package-diagram.puml` | `specs/08-package-diagram.md` | 7 | 包图 |
| `10-sequence-diagrams.puml`（实验二拆成 3 个文件） | `specs/10-sequence-borrow-book.md` + `specs/11-sequence-return-book.md` + `specs/12-sequence-reserve-book.md` | 3 | 顺序图 |
| `13-database-design.puml`（ER 图） | `specs/13-database-design.md` | 1 | ER 图 |
| （无单独文件） | `specs/03-use-cases.md` §5 | 1 | 用例关系图 |
| **合计** | | **24** | |

说明：实验二只要求“至少有办理借书、办理还书、预约图书三个顺序图”，本项目正好是 `10`/`11`/`12` 三个文件；实验概述要求的 UML 类型是用例图、类图、包图、顺序图（数据库设计另含 ER 图），**没有要求活动图/状态图**，本项目未交付这两类，不构成缺失。

## 3. 如需转成 PlantUML

若教师坚持要 `.puml` 实体文件，按上表逐项转换即可，**不需要改动任何正文内容**：

- 每个 ` ```mermaid ` 块替换为 `@startuml` … `@enduml`；
- 用例图：`usecase` / 参与者 `actor`；
- 类图：`class` / 关系 `-->`、`--|>`；
- 包图：`package` / 依赖 `..>`；
- 顺序图：`participant` / `->>`；
- ER 图：`entity` / 关系 `||--o{`。

## 4. 结论

- **内容层面**：24 张图齐全，覆盖用例、用例关系、领域类、包、三个关键顺序、ER。
- **格式层面**：与总述的 `.puml` 字样不一致，但符合工具链说明书与项目 constitution；属于“可解释的格式差异”，不是“缺图”。
- **补救成本**：若必须转换，约 1 小时机械转换；不建议为此重写规格正文。
