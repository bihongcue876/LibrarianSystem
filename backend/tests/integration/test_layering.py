"""分层与规格约束校验（`16-tasks.md` §0.2、`15-test-plan.md` §5）。

这些检查**用代码执行**，而不是靠人工 grep——把架构约束变成可回归的测试。

**实现方式**：用 `ast` 解析真实的 `import` / `from ... import` 语句，
而不是字符串匹配。字符串匹配会把 **docstring 里对约束的说明文字**误判为违规
（例如领域层文件头部写着"本包不得导入 sqlalchemy"——那是在声明约束，不是违规）。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"

#: 领域层不得导入的模块前缀（含框架与任何外层）
DOMAIN_FORBIDDEN = ("fastapi", "sqlalchemy", "app.application", "app.infrastructure")
#: 实体不得依赖的领域内子包（包图规则 D-7）
ENTITY_FORBIDDEN = ("app.domain.domain_services", "app.domain.factories")

#: 规则数值不得出现在策略对象的**代码**中（BR-049）
RULE_LITERAL_PATTERN = re.compile(r"(==\s*(5|10|15|20)\b)|(\b0\.2\b)|(\b0\.5\b)|(\b1\.0\b)")


def _py_files(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.py"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def imported_modules(path: Path) -> list[tuple[int, str]]:
    """返回 `[(行号, 被导入的模块名)]`。只取真实的 import 语句。"""
    tree = ast.parse(_read(path), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # 相对导入按包内处理，跳过
                continue
            if node.module:
                found.append((node.lineno, node.module))
    return found


def import_violations(folder: Path, forbidden: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in _py_files(folder):
        for lineno, module in imported_modules(path):
            if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden):
                violations.append(f"{path.relative_to(BACKEND)}:{lineno}: import {module}")
    return violations


def rule_literal_hits(folder: Path) -> list[str]:
    """检查代码中是否硬编码了规则数值（`ast` 层面：只查常量与比较）。"""
    hits: list[str] = []
    for path in _py_files(folder):
        source = _read(path)
        tree = ast.parse(source, filename=str(path))
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if RULE_LITERAL_PATTERN.search(repr(node.value)):
                    # 排除 True/False（本身是 int 子类）与 0/1 这类结构性常量
                    if node.value in (0, 1):
                        continue
                    hits.append(
                        f"{path.relative_to(BACKEND)}:{node.lineno}: "
                        f"字面量 {node.value!r} — {lines[node.lineno - 1].strip()}"
                    )
    return hits


class TestLayerPurity:
    """R-3：领域层零框架依赖（宪法第五条 / ADR-05）。"""

    def test_domain_imports_no_framework_or_outer_layer(self):
        violations = import_violations(APP / "domain", DOMAIN_FORBIDDEN)
        assert violations == [], "领域层出现框架或外层导入:\n" + "\n".join(violations)

    def test_domain_imports_are_stdlib_or_domain_only(self):
        """领域层的导入只应来自标准库与本包。"""
        allowed_prefixes = ("app.domain",)
        stdlib_ok = {
            "__future__", "abc", "collections", "collections.abc", "dataclasses", "datetime",
            "decimal", "enum", "itertools", "re", "typing", "types", "uuid", "math", "functools",
        }
        violations: list[str] = []
        for path in _py_files(APP / "domain"):
            for lineno, module in imported_modules(path):
                root = module.split(".")[0]
                if module.startswith(allowed_prefixes) or module in stdlib_ok or root in stdlib_ok:
                    continue
                violations.append(f"{path.relative_to(BACKEND)}:{lineno}: import {module}")
        assert violations == [], "领域层出现非预期依赖:\n" + "\n".join(violations)

    """D-7：`entities/` 不得依赖 `domain_services/` 与 `factories/`。"""

    def test_entities_do_not_depend_on_services_or_factories(self):
        violations = import_violations(APP / "domain" / "entities", ENTITY_FORBIDDEN)
        assert violations == [], "实体反向依赖服务或工厂:\n" + "\n".join(violations)

    """R-1：表现层路由不得依赖基础设施层。"""

    def test_routers_do_not_import_infrastructure(self):
        violations = import_violations(APP / "presentation" / "routers", ("app.infrastructure",))
        assert violations == [], "路由直接依赖基础设施层:\n" + "\n".join(violations)

    def test_presentation_infrastructure_imports_are_confined_to_dependencies(self):
        """`dependencies.py` 是**唯一**允许的装配点（依赖倒置）。"""
        violations = import_violations(APP / "presentation", ("app.infrastructure",))
        offenders = [item for item in violations if "dependencies.py" not in item]
        assert offenders == [], "表现层除装配点外依赖了基础设施层:\n" + "\n".join(offenders)

    """R-2：应用层不得依赖基础设施层的具体类。"""

    def test_application_does_not_import_infrastructure(self):
        violations = import_violations(APP / "application", ("app.infrastructure",))
        assert violations == [], "应用层直接依赖基础设施层:\n" + "\n".join(violations)

    def test_application_services_depend_on_ports(self):
        """应用服务必须经 `ports` 的 Protocol 访问持久化与安全能力。"""
        services = APP / "application" / "services"
        text = "\n".join(_read(path) for path in _py_files(services))
        assert "app.application.ports" in text
        assert "SqlAlchemy" not in text

    def test_ports_declare_repository_and_security_protocols(self):
        from app.application import ports

        for name in (
            "ReaderRepository",
            "CardRepository",
            "CatalogRepository",
            "LoanRepository",
            "ReservationRepository",
            "FineRepository",
            "PolicyRepository",
            "PasswordHasher",
            "TokenIssuer",
        ):
            assert hasattr(ports, name), f"缺少端口 {name}"


class TestBusinessRuleNotHardcoded:
    """BR-049：规则数值必须存库，代码中不得出现硬编码分支。"""

    def test_policies_have_no_rule_literals(self):
        violations = rule_literal_hits(APP / "domain" / "policies")
        assert violations == [], "策略对象中硬编码了规则数值:\n" + "\n".join(violations)

    def test_domain_services_have_no_rule_literals(self):
        """领域服务也不得硬编码借阅/罚款数值。"""
        violations = rule_literal_hits(APP / "domain" / "domain_services")
        assert violations == [], "领域服务中硬编码了规则数值:\n" + "\n".join(violations)

    def test_queue_cap_is_named_constant(self):
        """队列上限 5 是结构常量而非可配置规则，但必须以**具名常量**出现并注明依据。"""
        from app.domain.domain_services.reservation_queue_service import MAX_QUEUE_SIZE

        assert MAX_QUEUE_SIZE == 5
        text = _read(APP / "domain" / "domain_services" / "reservation_queue_service.py")
        assert "BR-022" in text, "队列上限应注明规则依据"

    def test_rule_values_live_in_seed_script(self):
        """规则数值应作为**数据**出现在初始化脚本中。"""
        seed = _read(BACKEND / "scripts" / "init_db.py")
        assert "BORROW_POLICY_SEED" in seed
        assert "FINE_RULE_SEED" in seed
        assert "0.50" in seed and "100.00" in seed


class TestDatabaseDesign:
    """与 `13-database-design.md` 的一致性。"""

    def test_table_count_is_eleven(self):
        from app.infrastructure.db.base import Base
        from app.infrastructure.models import load_all_models

        load_all_models()
        assert len(Base.metadata.tables) == 11

    def test_expected_table_names(self):
        from app.infrastructure.db.base import Base
        from app.infrastructure.models import load_all_models

        load_all_models()
        expected = {
            "readers",
            "librarians",
            "system_admins",
            "borrow_cards",
            "book_titles",
            "library_items",
            "loans",
            "reservations",
            "fine_records",
            "borrow_policies",
            "fine_rules",
        }
        assert set(Base.metadata.tables) == expected

    def test_single_table_inheritance_markers(self):
        """`readers` 与 `library_items` 各自承载单表继承（D-49、D-50）。"""
        from app.infrastructure.db.base import Base
        from app.infrastructure.models import load_all_models

        load_all_models()
        assert "reader_type" in Base.metadata.tables["readers"].columns
        assert "student_type" in Base.metadata.tables["readers"].columns
        assert "item_type" in Base.metadata.tables["library_items"].columns

    def test_loans_status_check_only_two_states(self):
        """`OVERDUE` 是派生状态，库层只允许两态。"""
        from app.infrastructure.db.base import Base
        from app.infrastructure.models import load_all_models

        load_all_models()
        names = {
            constraint.name
            for constraint in Base.metadata.tables["loans"].constraints
            if constraint.name
        }
        assert "ck_loans_status" in names

    def test_partial_unique_indexes_exist(self):
        """三个部分唯一索引：借阅证 active、ISBN active、预约 effective。"""
        from app.infrastructure.db.base import Base
        from app.infrastructure.models import load_all_models

        load_all_models()
        names = {index.name for table in Base.metadata.tables.values() for index in table.indexes}
        assert {
            "uq_borrow_cards_active_reader",
            "uq_book_titles_isbn_active",
            "uq_reservations_active_reader_title",
        } <= names

    def test_money_columns_are_text(self):
        """金额列必须为 TEXT（`MoneyType`），避免 SQLite REAL 引入浮点误差（Q-04）。"""
        from sqlalchemy import Text

        from app.infrastructure.db.base import Base, MoneyType
        from app.infrastructure.models import load_all_models

        load_all_models()
        money_columns = [
            column
            for table in Base.metadata.tables.values()
            for column in table.columns
            if isinstance(column.type, MoneyType)
        ]
        assert money_columns, "未找到任何金额列"
        for column in money_columns:
            assert isinstance(column.type.impl, Text), f"{column} 的底层类型不是 TEXT"


class TestTestLayering:
    """`15-test-plan.md` §1.1：单测目录不得依赖数据库与 Web 框架。"""

    def test_unit_tests_do_not_import_frameworks(self):
        violations = import_violations(
            BACKEND / "tests" / "unit", ("fastapi", "sqlalchemy", "starlette")
        )
        assert violations == [], "单元测试依赖了数据库或 Web 框架:\n" + "\n".join(violations)

    def test_test_directories_exist(self):
        assert (BACKEND / "tests" / "unit").is_dir()
        assert (BACKEND / "tests" / "integration").is_dir()
