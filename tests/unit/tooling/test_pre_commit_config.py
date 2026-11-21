"""The freshness hook fires on the generator's inputs and on generated output (generator-package D-27, D-29, DEC-10).

The generator's inputs are its modules, templates, model and lint config, the library's model and
the toy. Not every manifest input: the library's ``schema/services/schema.py`` and ``schema_structure.py``
are manifest inputs the hook does not match.
"""

import re

import pytest
import yaml

from tests.conftest import TESTS_ROOT_DIR

CONFIG = TESTS_ROOT_DIR.parent / ".pre-commit-config.yaml"
HOOK_ID = "rp-generate-check"


def _files_pattern() -> re.Pattern[str]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    hooks = [h for repo in config["repos"] for h in repo["hooks"] if h["id"] == HOOK_ID]
    assert len(hooks) == 1, f"{CONFIG.name} must declare the hook {HOOK_ID} once"
    return re.compile(hooks[0]["files"])  # pre-commit applies it with re.search


@pytest.mark.parametrize(
    "path",
    [
        "rdf_persistence/model/metamodel.yaml",
        "rdf_persistence_generation/model/rp_generation.yaml",
        "rdf_persistence_generation/steps.py",
        "rdf_persistence_generation/pipeline.py",
        "rdf_persistence_generation/extensions/x.py",
        "rdf_persistence_generation/templates/x.jinja",
        "rdf_persistence_generation/lint.yaml",
        "tests/fixtures/library/model/library.yaml",
    ],
)
def test_the_hook_fires_on_a_manifest_input(path: str) -> None:
    assert _files_pattern().search(path), f"{path} is a generator input but does not run the hook"


@pytest.mark.parametrize(
    "path",
    [
        "rdf_persistence/generated/models.py",
        "rdf_persistence_generation/generated/rp_generation.py",
        "tests/fixtures/library/domain/generated/models.py",
    ],
)
def test_the_hook_fires_on_generated_output_on_purpose(path: str) -> None:
    """The ``.*/generated/`` branch catches a hand edit of generated code (PD-26)."""
    assert _files_pattern().search(path), f"{path} is generated output and must run the hook"


@pytest.mark.parametrize(
    "path",
    [
        "rdf_persistence_generation/testkit/freshness.py",
        "rdf_persistence_generation/testkit/strategies.py",
        "rdf_persistence/persistence/services/mapper.py",
        "tests/unit/tooling/test_lanes.py",
    ],
)
def test_the_hook_stays_quiet_on_what_is_no_manifest_input(path: str) -> None:
    assert not _files_pattern().search(path), f"{path} is no manifest input; the hook must not fire"
