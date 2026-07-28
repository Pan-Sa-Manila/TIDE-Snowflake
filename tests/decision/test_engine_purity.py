"""Architectural gate: the engine stays pure.

AGENTS.md §3 and .cortex/skills/decision-engine: `tide_decision/` has zero
Snowflake imports and no I/O. That is what lets this suite run with no account,
and it is easy to break by reflex — so it is asserted, not just documented.
"""

import ast
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[2] / "tide_decision"

# Anything that would drag in a database, a network, or a clock-of-record.
FORBIDDEN_ROOTS = {
    "snowflake", "snowpark", "_snowflake",
    "requests", "urllib", "urllib3", "http", "httpx", "socket",
    "boto3", "sqlalchemy", "psycopg2", "pandas", "pydantic",
    "openai", "anthropic",
}

ALLOWED_ROOTS = {"__future__", "dataclasses", "enum", "typing", "datetime", "tide_decision"}


def _engine_modules() -> list[Path]:
    modules = sorted(ENGINE_DIR.glob("*.py"))
    assert modules, f"no engine modules found under {ENGINE_DIR}"
    return modules


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_engine_has_no_snowflake_or_network_imports():
    for module in _engine_modules():
        offenders = _imported_roots(module) & FORBIDDEN_ROOTS
        assert not offenders, f"{module.name} imports {sorted(offenders)}"


def test_engine_imports_stay_on_the_allowlist():
    """A new dependency in the engine is an architecture decision, not a detail."""
    for module in _engine_modules():
        unexpected = _imported_roots(module) - ALLOWED_ROOTS
        assert not unexpected, (
            f"{module.name} imports {sorted(unexpected)} — add it to ALLOWED_ROOTS "
            f"here (and to docs/ARCHITECTURE.md §8) if that is intended"
        )
