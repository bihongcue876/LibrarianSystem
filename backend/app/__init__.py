"""AI时代图书管理系统 —— 后端应用包。

分层结构（`07-architecture.md` §2）：

- `presentation/`  表现层：路由（Controller）、DTO、鉴权守卫
- `application/`   应用层：应用服务、Repository 接口（ports）、事务边界
- `domain/`        领域层：实体、值对象、领域服务、策略对象（**零框架依赖**）
- `infrastructure/` 基础设施层：ORM、Repository 实现、Mapper、安全

依赖方向：`presentation → application → domain`，`infrastructure` 实现上层定义的接口。
"""

__version__ = "0.1.0"
