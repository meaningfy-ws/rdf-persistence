"""Pytest plugin: stop the session when generated code is stale or was edited by hand (PD-26).

Enable it in the root conftest with ``pytest_plugins = ["rdf_persistence.testkit.freshness"]``. It
reads the ``pyproject.toml`` files named by the ini option ``rp_generate_projects`` (one per line,
relative to the rootdir; default: the rootdir's own) and compares each target's manifest with the
files now. It imports neither the ``generate`` extra nor testcontainers.
"""

from pathlib import Path

import pytest

from rdf_persistence.generation.config import read_targets
from rdf_persistence.generation.exceptions import ConfigError
from rdf_persistence.generation.generated.rp_generation import GenerationTarget
from rdf_persistence.generation.manifest import fix_hint, stale_targets
from rdf_persistence.generation.problems import format_problem

PROJECTS_OPTION = "rp_generate_projects"
DEFAULT_PROJECT = "pyproject.toml"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(
        PROJECTS_OPTION,
        type="linelist",
        default=[],
        help="pyproject.toml files whose rp-generate output must be fresh (default: the rootdir's)",
    )


def _project_report(project: Path) -> tuple[list[str], list[GenerationTarget]]:
    """The report lines of ``project`` and its stale targets (none when its configuration is wrong)."""
    try:
        stale = stale_targets(read_targets(project), project.parent)
    except ConfigError as error:
        return [str(error)], []
    lines = [format_problem(problem) for _, problems in stale for problem in problems]
    return lines, [target for target, _ in stale]


def pytest_sessionstart(session: pytest.Session) -> None:
    config = session.config
    projects = config.getini(PROJECTS_OPTION) or [DEFAULT_PROJECT]
    lines: list[str] = []
    stale: list[GenerationTarget] = []
    for project in projects:
        project_lines, project_stale = _project_report(config.rootpath / project)
        lines += [f"{project}: {line}" for line in project_lines]
        stale += project_stale
    if lines:
        hint = [fix_hint(stale)] if stale else []  # a configuration error gets none (PD-6)
        pytest.exit("\n".join(["generated code is not fresh:", *lines, *hint]), returncode=1)
