"""A consumer's manifest still naming ``rdf_persistence/generation/...`` is stale, with the hint (PD-4, RISK-2).

A consumer's committed ``rp-manifest.json`` names the generator's pre-move folder. The check and
the freshness plugin must stop on it and name the consumer's regenerate command.
"""

import json
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main
from tests.generator.unit.golden import (
    DEFAULT_HINT,
    INI,
    MANIFEST,
    TEST,
    check,
    make_project,
    project,
)

NEW_PREFIX = "rdf_persistence_generation/"
OLD_PREFIX = "rdf_persistence/generation/"
NEW_PLUGIN = "rdf_persistence_generation.testkit.freshness"


def rewrite_inputs_to_the_old_folder(manifest: Path) -> list[str]:
    """Rename every recorded generator input to its pre-move path, hashes kept; return the old paths."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    old: list[str] = []
    for entry in data["inputs"]:
        if entry["path"].startswith(NEW_PREFIX):
            entry["path"] = OLD_PREFIX + entry["path"].removeprefix(NEW_PREFIX)
            old.append(entry["path"])
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return old


def test_a_manifest_naming_the_old_generator_folder_is_stale_with_the_regenerate_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Error matrix: a consumer manifest naming ``rdf_persistence/generation/...`` is STALE."""
    pyproject = project(tmp_path)
    assert main(["--project", str(pyproject)]) == 0, "the project must generate"
    old = rewrite_inputs_to_the_old_folder(pyproject.parent / MANIFEST)
    assert old, "the manifest had no generator input to rename"

    code, error = check(pyproject, capsys)

    assert code == 1, "a manifest with the pre-move paths passed the check"
    assert f"stale input: {old[0]} (removed)" in error, f"the old path is not named:\n{error}"
    assert f"stale input: {NEW_PREFIX}" in error, "the new path is not reported as new"
    assert DEFAULT_HINT in error, "the regenerate command is not named"


@pytest.mark.slow
def test_a_consumer_manifest_with_the_old_paths_stops_a_session_with_the_hint(
    pytester: pytest.Pytester,
) -> None:
    """Error matrix: the plugin, on a manifest from before the move, stops and names the old path."""
    make_project(pytester.path)
    pytester.makeini(INI.replace("    other/pyproject.toml\n", ""))
    pytester.makeconftest(f'pytest_plugins = ["{NEW_PLUGIN}"]\n')
    pytester.makepyfile(test_it=TEST)
    old = rewrite_inputs_to_the_old_folder(pytester.path / MANIFEST)

    result = pytester.runpytest_subprocess()

    out = result.stdout.str()
    assert result.ret == 1, f"a pre-move manifest let the tests run:\n{out}"
    assert old[0] in out, f"the old path is not named:\n{out}"
    assert DEFAULT_HINT in out, "the regenerate command is not named"
