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
from rdf_persistence.generation.manifest import FIX_HINT, freshness_problems

PROJECTS_OPTION = "rp_generate_projects"
DEFAULT_PROJECT = "pyproject.toml"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(
        PROJECTS_OPTION,
        type="linelist",
        default=[],
        help="pyproject.toml files whose rp-generate output must be fresh (default: the rootdir's)",
    )


def _project_problems(project: Path) -> list[str]:
    try:
        return freshness_problems(read_targets(project), project.parent)
    except ConfigError as error:
        return [str(error)]


def pytest_sessionstart(session: pytest.Session) -> None:
    config = session.config
    projects = config.getini(PROJECTS_OPTION) or [DEFAULT_PROJECT]
    lines = [
        f"{project}: {problem}"
        for project in projects
        for problem in _project_problems(config.rootpath / project)
    ]
    if lines:
        pytest.exit("\n".join(["generated code is not fresh:", *lines, FIX_HINT]), returncode=1)
