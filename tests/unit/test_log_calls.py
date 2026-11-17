"""Every log call in the package is in the one logging style (PD-9, DEC-8)."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "rdf_persistence"
LEVELS = frozenset({"debug", "info", "warning", "error", "exception", "critical"})
LOGGER_NAME = "log"
LOGGER_FACTORY = ast.dump(ast.parse("logging.getLogger(__name__)", mode="eval").body)
CONTEXT_FUNCTION = "log_extra"


def _is_log_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in LEVELS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == LOGGER_NAME
    )


def _is_get_logger(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
    return name == "getLogger"


def _is_constant_message(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_log_extra_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == CONTEXT_FUNCTION
    )


def _call_reasons(call: ast.Call) -> list[str]:
    reasons = []
    if len(call.args) != 1 or any(isinstance(arg, ast.Starred) for arg in call.args):
        reasons.append(f"log call takes {len(call.args)} positional arguments, not exactly one")
    elif not _is_constant_message(call.args[0]):
        reasons.append("log message is not a string literal (no f-string, no % arguments)")
    extras = [keyword for keyword in call.keywords if keyword.arg == "extra"]
    if not extras:
        reasons.append(f"log call has no extra={CONTEXT_FUNCTION}(...)")
    reasons.extend(
        f"extra= is not a {CONTEXT_FUNCTION}(...) call"
        for keyword in extras
        if not _is_log_extra_call(keyword.value)
    )
    return reasons


def _logger_reason(statement: ast.stmt) -> str | None:
    if not isinstance(statement, ast.Assign | ast.AnnAssign):
        return None
    value = statement.value
    if value is None or not _is_get_logger(value):
        return None
    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
    named_log = (
        len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id == LOGGER_NAME
    )
    if named_log and ast.dump(value) == LOGGER_FACTORY:
        return None
    return f"module-level logger is not exactly {LOGGER_NAME} = logging.getLogger(__name__)"


def violations(source: str, path: str) -> list[str]:
    """The ``path:line: reason`` lines for each way ``source`` leaves the logging style."""
    tree = ast.parse(source)
    found = [
        (statement.lineno, reason)
        for statement in tree.body
        if (reason := _logger_reason(statement))
    ]
    for node in ast.walk(tree):
        if _is_log_call(node):
            found.extend((node.lineno, reason) for reason in _call_reasons(node))
    return [f"{path}:{line}: {reason}" for line, reason in sorted(found)]


def package_files() -> list[Path]:
    """The package's modules, generated code excluded."""
    return sorted(
        path for path in ROOT.rglob("*.py") if "generated" not in path.relative_to(ROOT).parts
    )


GOOD = """\
import logging

log = logging.getLogger(__name__)


def run(name):
    log.info("dropped", extra=log_extra(LogContext(db_namespace=name)))
    log.error("failed", extra=log_extra(LogContext(step="run")), exc_info=True)
"""

BAD_SOURCES = {
    "f-string message": (
        'import logging\nlog = logging.getLogger(__name__)\nlog.info(f"dropped {name}")\n',
        3,
    ),
    "percent arguments": (
        'import logging\nlog = logging.getLogger(__name__)\nlog.warning("m %s", x)\n',
        3,
    ),
    "percent expression": (
        'import logging\nlog = logging.getLogger(__name__)\nlog.warning("m %s" % x)\n',
        3,
    ),
    "dict extra": (
        'import logging\nlog = logging.getLogger(__name__)\nlog.info("m", extra={"step": 1})\n',
        3,
    ),
    "no extra": (
        'import logging\nlog = logging.getLogger(__name__)\nlog.info("m")\n',
        3,
    ),
    "other logger name": ('import logging\nlogger = logging.getLogger("x")\n', 2),
    "logger without __name__": ('import logging\nlog = logging.getLogger("x")\n', 2),
}


@pytest.mark.parametrize(("source", "line"), BAD_SOURCES.values(), ids=BAD_SOURCES.keys())
def test_a_departure_from_the_style_is_reported_with_file_and_line(
    source: str, line: int
) -> None:  # TC-24
    found = violations(source, "pkg/mod.py")

    assert found, "the departure is reported"
    assert all(item.startswith(f"pkg/mod.py:{line}: ") for item in found)


def test_a_source_in_the_new_style_has_no_violation() -> None:  # TC-24
    assert violations(GOOD, "pkg/mod.py") == []


def test_every_log_call_in_the_package_is_in_the_style() -> None:  # TC-23
    found = [
        item
        for path in package_files()
        for item in violations(path.read_text(), str(path.relative_to(ROOT.parent)))
    ]

    assert found == [], f"{len(found)} violations:\n" + "\n".join(found)
