"""表现层（`07-architecture.md` §2.1）。

**约束**：不得依赖 `infrastructure`（包图规则 R-1）——服务实例由
`dependencies.py` 注入，本层只认识应用层接口。
"""

__all__: list[str] = []
