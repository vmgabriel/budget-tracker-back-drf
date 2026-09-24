"""Executable safeguards for the dependency rule of the domain layer."""

import ast
from pathlib import Path

import pytest

FORBIDDEN_DOMAIN_IMPORTS = {"celery", "django", "psycopg", "rest_framework"}

pytestmark = pytest.mark.unit


def _imported_modules(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_modules_do_not_import_frameworks() -> None:
    project_root = Path(__file__).resolve().parents[2]
    domain_files = sorted((project_root / "apps").glob("*/domain/**/*.py"))
    violations: dict[Path, set[str]] = {}

    for source_path in domain_files:
        forbidden = {
            module
            for module in _imported_modules(source_path)
            if module.split(".", maxsplit=1)[0] in FORBIDDEN_DOMAIN_IMPORTS
        }
        if forbidden:
            violations[source_path.relative_to(project_root)] = forbidden

    assert not violations, f"Framework imports found in domain modules: {violations}"


def test_shared_domain_modules_do_not_import_frameworks() -> None:
    project_root = Path(__file__).resolve().parents[2]
    shared_domain_files = sorted((project_root / "shared" / "domain").glob("**/*.py"))
    violations: dict[Path, set[str]] = {}

    for source_path in shared_domain_files:
        forbidden = {
            module
            for module in _imported_modules(source_path)
            if module.split(".", maxsplit=1)[0] in FORBIDDEN_DOMAIN_IMPORTS
        }
        if forbidden:
            violations[source_path.relative_to(project_root)] = forbidden

    assert not violations, f"Framework imports found in shared domain: {violations}"


def test_application_modules_depend_only_inward() -> None:
    project_root = Path(__file__).resolve().parents[2]
    application_files = sorted((project_root / "apps").glob("*/application/**/*.py"))
    violations: dict[Path, set[str]] = {}

    for source_path in application_files:
        forbidden: set[str] = set()
        for module in _imported_modules(source_path):
            if module.split(".", maxsplit=1)[0] in FORBIDDEN_DOMAIN_IMPORTS:
                forbidden.add(module)
                continue
            parts = module.split(".")
            if (
                len(parts) >= 3
                and parts[0] == "apps"
                and parts[2] in {"infrastructure", "interfaces"}
            ):
                forbidden.add(module)
        if forbidden:
            violations[source_path.relative_to(project_root)] = forbidden

    assert not violations, f"Outward imports found in application modules: {violations}"
