"""The generation manifest and `rp-generate --check` (PD-26): stale input, edited output, version."""

import subprocess
import sys
from pathlib import Path

import pytest

from rdf_persistence import generation
from rdf_persistence.generation import manifest as manifest_module
from rdf_persistence.generation.cli import main
from rdf_persistence.generation.config import read_targets
from rdf_persistence.generation.generated.rp_generation import GenerationManifest, GenerationTarget

from .test_generate_cli import PYPROJECT, SCHEMA, project

DEFAULT_HINT = "run `rp-generate` to regenerate, then commit the result"
MANIFEST = Path("app/generated/rp-manifest.json")
OUTPUT = "app/generated/m.py"
PART = SCHEMA.replace("name: m", "name: part").replace("Thing:", "Part:").replace("things", "parts")
NESTED = """
[[tool.rp-generate]]
schema = "m.yaml"
package = "app.generated"

[[tool.rp-generate]]
schema = "part.yaml"
package = "app.generated.part"
"""
WITH_PART = SCHEMA.replace("  - linkml:types", "  - linkml:types\n  - part")


@pytest.fixture
def generated(tmp_path: Path) -> Path:
    """A generated one-schema project; returns its pyproject.toml."""
    pyproject = project(tmp_path)
    assert main(["--project", str(pyproject)]) == 0, "the project must generate"
    return pyproject


def read_manifest(pyproject: Path) -> GenerationManifest:
    return GenerationManifest.model_validate_json(
        (pyproject.parent / MANIFEST).read_text(encoding="utf-8")
    )


def check(pyproject: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    capsys.readouterr()
    code = main(["--project", str(pyproject), "--check"])
    return code, capsys.readouterr().err


def test_a_fresh_run_passes_the_check(generated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, error = check(generated, capsys)
    assert code == 0, f"a fresh run failed the check: {error}"


def test_the_manifest_lists_sorted_posix_paths_with_raw_byte_hashes(generated: Path) -> None:
    manifest = read_manifest(generated)
    inputs = {entry.path: entry.sha256 for entry in manifest.inputs}
    paths = [entry.path for entry in manifest.inputs]
    assert paths == sorted(paths), "inputs are not sorted by path"
    assert OUTPUT in [e.path for e in manifest.outputs], "the generated module is not an output"
    assert str(MANIFEST) not in [e.path for e in manifest.outputs], "the manifest lists itself"
    assert inputs["m.yaml"] == manifest_module.sha256_of(generated.parent / "m.yaml"), (
        "the hash is not over the file's bytes"
    )


def test_package_inputs_are_recorded_under_the_package_name(generated: Path) -> None:
    paths = [entry.path for entry in read_manifest(generated).inputs]
    assert "rdf_persistence/model/rp_core.yaml" in paths, "the metamodel is not an input"
    assert "rdf_persistence/generation/cli.py" in paths, "the generator code is not an input"
    assert any(p.startswith("rdf_persistence/generation/templates/") for p in paths), (
        "the templates are not inputs"
    )


def test_every_module_that_decides_how_a_schema_is_read_is_an_input(generated: Path) -> None:
    paths = {entry.path for entry in read_manifest(generated).inputs}
    readers = {
        f"rdf_persistence/services/{module.name}"
        for module in manifest_module.SERVICES_DIR.glob("schema*.py")
    }
    assert {
        "rdf_persistence/services/schema.py",
        "rdf_persistence/services/schema_structure.py",
    } <= readers, "the scan found no schema reader"
    assert readers <= paths, f"not inputs: {sorted(readers - paths)}"


def test_linkml_types_and_the_generated_folder_are_not_inputs(generated: Path) -> None:
    paths = [entry.path for entry in read_manifest(generated).inputs]
    assert not [p for p in paths if "types.yaml" in p], "linkml:types is an input"
    assert not [p for p in paths if p.startswith("rdf_persistence/generation/generated/")], (
        "the toolkit's own generated folder is an input"
    )


def test_a_schema_changed_without_regenerating_is_stale_and_named(
    generated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    schema = generated.parent / "m.yaml"
    schema.write_text(schema.read_text() + "# changed\n", encoding="utf-8")
    code, error = check(generated, capsys)
    assert code == 1, "a stale input passed the check"
    assert "m.yaml" in error, "the changed schema is not named"
    assert DEFAULT_HINT in error, "the fixing command is not named"


def test_a_generated_file_edited_by_hand_is_named(
    generated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = generated.parent / OUTPUT
    output.write_text(output.read_text() + "# by hand\n", encoding="utf-8")
    code, error = check(generated, capsys)
    assert code == 1, "an edited output passed the check"
    assert OUTPUT in error, "the edited file is not named"
    assert DEFAULT_HINT in error, "the fixing command is not named"


def test_a_missing_output_is_named(generated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (generated.parent / OUTPUT).unlink()
    code, error = check(generated, capsys)
    assert code == 1, "a missing output passed the check"
    assert OUTPUT in error, "the missing file is not named"


def test_a_project_never_generated_fails_the_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, error = check(project(tmp_path), capsys)
    assert code == 1, "a project without a manifest passed the check"
    assert DEFAULT_HINT in error, "the fixing command is not named"


def test_a_changed_linkml_version_is_stale(
    generated: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(manifest_module, "linkml_version", lambda: "0.0.1")
    code, error = check(generated, capsys)
    assert code == 1, "a different linkml version passed the check"
    assert "linkml" in error, "the version is not named"


def test_without_the_extra_the_comparison_runs_and_the_version_is_not_compared(
    generated: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in [m for m in sys.modules if m.startswith("linkml.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "linkml", None)
    monkeypatch.delitem(sys.modules, "rdf_persistence.generation.steps", raising=False)
    monkeypatch.delattr(
        generation, "steps", raising=False
    )  # a from-import would find the attribute
    monkeypatch.setattr(manifest_module, "linkml_version", lambda: None)
    code, error = check(generated, capsys)
    assert code == 0, f"the comparison failed without the extra: {error}"
    (generated.parent / "m.yaml").write_text(SCHEMA + "# changed\n", encoding="utf-8")
    code, error = check(generated, capsys)
    assert code == 1, "a stale input passed without the extra"
    assert "m.yaml" in error, "the changed schema is not named"


def test_a_second_run_deletes_what_it_no_longer_generates_and_keeps_foreign_files(
    tmp_path: Path,
) -> None:
    pyproject = project(tmp_path, WITH_PART)
    (tmp_path / "part.yaml").write_text(PART, encoding="utf-8")
    assert main(["--project", str(pyproject)]) == 0, "the two-module project must generate"
    part = tmp_path / "app/generated/part.py"
    assert part.is_file(), "the first run did not write the imported module"
    foreign = tmp_path / "app/generated/notes.txt"
    foreign.write_text("mine", encoding="utf-8")
    (tmp_path / "m.yaml").write_text(SCHEMA, encoding="utf-8")
    assert main(["--project", str(pyproject)]) == 0, "the second run failed"
    assert not part.exists(), "a file the schema no longer generates was kept"
    assert foreign.read_text() == "mine", "a file the manifest does not list was touched"


def test_nested_target_folders_keep_each_manifest_apart(tmp_path: Path) -> None:
    pyproject = project(tmp_path, pyproject=NESTED)
    (tmp_path / "part.yaml").write_text(PART, encoding="utf-8")
    assert main(["--project", str(pyproject)]) == 0, "the two targets must generate"
    outer = GenerationManifest.model_validate_json(
        (tmp_path / "app/generated/rp-manifest.json").read_text()
    )
    assert not [e for e in outer.outputs if "/part/" in e.path], (
        "the outer manifest lists the inner"
    )
    assert (tmp_path / "app/generated/part/rp-manifest.json").is_file(), "no inner manifest"


NAMED = 'regenerate-command = "make generate-models"\n'
TWO_COMMANDS = """
[[tool.rp-generate]]
schema = "m.yaml"
package = "app.generated"
regenerate-command = "make a"

[[tool.rp-generate]]
schema = "part.yaml"
package = "app.generated.part"
regenerate-command = "make b"
"""


def stale(tmp_path: Path, pyproject: str, *changed: str) -> Path:
    """A generated project (schemas m.yaml and part.yaml) whose ``changed`` schemas then change."""
    path = project(tmp_path, SCHEMA, pyproject)
    (tmp_path / "part.yaml").write_text(PART, encoding="utf-8")
    assert main(["--project", str(path)]) == 0, "the project must generate"
    for name in changed:
        file = tmp_path / name
        file.write_text(file.read_text() + "# changed\n", encoding="utf-8")
    return path


def test_without_a_command_the_hint_names_rp_generate(
    generated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (generated.parent / "m.yaml").write_text(SCHEMA + "# changed\n", encoding="utf-8")
    _, error = check(generated, capsys)
    assert error.rstrip().endswith(DEFAULT_HINT), "the default command is not the hint"


def test_an_entry_names_its_own_command_in_the_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = stale(tmp_path, PYPROJECT + NAMED, "m.yaml")
    _, error = check(path, capsys)
    assert error.rstrip().endswith("run `make generate-models` to regenerate, then commit the result"), "the entry's command is not named"
    assert "rp-generate`" not in error, "the default is named beside the entry's command"


def test_the_hint_names_the_command_of_each_stale_entry_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = stale(tmp_path, TWO_COMMANDS, "m.yaml", "part.yaml")
    assert check(path, capsys)[1].rstrip().endswith("run `make a` or `make b` to regenerate, then commit the result"), "both not named"
    (tmp_path / "other").mkdir()
    path = stale(tmp_path / "other", TWO_COMMANDS, "part.yaml")
    assert check(path, capsys)[1].rstrip().endswith("run `make b` to regenerate, then commit the result"), "a fresh entry's is named"


def test_stale_targets_lists_only_the_targets_with_problems(
    tmp_path: Path,
) -> None:
    path = stale(tmp_path, TWO_COMMANDS, "part.yaml")
    targets = read_targets(path)
    ((target, problems),) = manifest_module.stale_targets(targets, tmp_path)
    assert target.regenerate_command == "make b", "the fresh target is listed"
    assert problems, "a stale target has no problem"
    assert manifest_module.freshness_problems(targets, tmp_path) == problems, "not the flattening"


def test_fix_hint_dedupes_commands_in_entry_order() -> None:
    targets = [
        GenerationTarget(schema_file="a", package="a", regenerate_command=c)
        for c in ("make b", None, "make b", "make a")
    ]
    assert manifest_module.fix_hint(targets) == "run `make b` or `rp-generate` or `make a` to regenerate, then commit the result"


def test_two_stale_entries_with_the_same_command_name_it_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = stale(tmp_path, TWO_COMMANDS.replace("make b", "make a"), "m.yaml", "part.yaml")
    _, error = check(path, capsys)
    assert error.count("to regenerate, then commit the result") == 1, "not exactly one hint"
    assert error.rstrip().endswith("run `make a` to regenerate, then commit the result"), "the shared command is not named once"


def test_a_stale_entry_without_a_command_and_one_with_name_both(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mixed = TWO_COMMANDS.replace('regenerate-command = "make a"\n', "")
    path = stale(tmp_path, mixed, "m.yaml", "part.yaml")
    assert check(path, capsys)[1].rstrip().endswith("run `rp-generate` or `make b` to regenerate, then commit the result"), "not both"


def test_the_installed_rp_generate_command_exits_1_and_hints_the_entry_command(
    tmp_path: Path,
) -> None:
    path = stale(tmp_path, PYPROJECT + NAMED, "m.yaml")
    command = Path(sys.executable).parent / "rp-generate"
    done = subprocess.run(
        [str(command), "--project", str(path), "--check"], capture_output=True, text=True
    )
    assert done.returncode == 1, f"exit code {done.returncode}: {done.stderr}"
    assert done.stderr.rstrip().endswith("run `make generate-models` to regenerate, then commit the result"), "the hint is not last"
    assert done.stdout == "", "a failed check wrote to stdout"


def test_a_fresh_project_through_the_installed_command_exits_0_silently(generated: Path) -> None:
    command = Path(sys.executable).parent / "rp-generate"
    done = subprocess.run(
        [str(command), "--project", str(generated), "--check"], capture_output=True, text=True
    )
    assert (done.returncode, done.stderr) == (0, ""), "a fresh check was not silent success"
