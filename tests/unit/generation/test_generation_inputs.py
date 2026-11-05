"""rp-generate validates its own inputs (PD-28): manifest, configured folders, staged files, exceptions."""

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from rdf_persistence.generation import steps
from rdf_persistence.generation.cli import build_parser, main
from rdf_persistence.generation.config import read_targets
from rdf_persistence.generation.exceptions import ConfigError, SchemaGenerationError, StepError
from rdf_persistence.generation.generated.rp_generation import (
    GeneratedFile,
    GenerationManifest,
    GenerationTarget,
    ManifestEntry,
)
from rdf_persistence.generation.pipeline import Run, render_step, stage
from rdf_persistence.services.schema import load_schema

from .test_freshness import MANIFEST, read_manifest
from .test_generate_cli import project

VALID_PATHS = ["a.py", "a/b/c.py", ".hidden/x", "rdf_persistence/model/rp.yaml", "a..b/c", "..x"]
INVALID_PATHS = ["", "/a", "../a", "a/../b", "a/..", "C:/a", "a\\b", "a//b", "./a", "a/", "."]
VALID_PACKAGES = ["app", "app.generated", "a_b.c1", "_p"]
INVALID_PACKAGES = ["", "a b", "a..b", "1a", "a-b", ".a", "a.", "a/b", 'a"; import os #']
FOLDER_FIELDS = ["schema_file", "python", "typescript", "diagrams"]
SHA = "0" * 64


def target(**fields: str) -> GenerationTarget:
    return GenerationTarget(**{"schema_file": "m.yaml", "package": "app", **fields})


@pytest.mark.parametrize("path", VALID_PATHS)
def test_a_relative_posix_path_is_a_manifest_path(path: str) -> None:
    assert ManifestEntry(path=path, sha256=SHA).path == path, f"{path!r} was refused"


@pytest.mark.parametrize("path", INVALID_PATHS)
def test_a_manifest_path_that_could_leave_the_project_is_refused(path: str) -> None:
    with pytest.raises(ValidationError):
        ManifestEntry(path=path, sha256=SHA)


@pytest.mark.parametrize("digest", ["", "0" * 63, "0" * 65, "A" * 64, "g" * 64, SHA + "\n"])
def test_a_hash_is_64_lowercase_hex_digits(digest: str) -> None:
    with pytest.raises(ValidationError):
        ManifestEntry(path="a.py", sha256=digest)


@pytest.mark.parametrize("field", FOLDER_FIELDS)
@pytest.mark.parametrize("path", VALID_PATHS)
def test_a_configured_path_may_be_relative(field: str, path: str) -> None:
    assert getattr(target(**{field: path}), field) == path, f"{path!r} was refused for {field}"


@pytest.mark.parametrize("field", FOLDER_FIELDS)
@pytest.mark.parametrize("path", INVALID_PATHS)
def test_a_configured_path_that_could_leave_the_project_is_refused(field: str, path: str) -> None:
    with pytest.raises(ValidationError):
        target(**{field: path})


@pytest.mark.parametrize("package", VALID_PACKAGES)
def test_a_dotted_identifier_is_a_package(package: str) -> None:
    assert target(package=package).package == package, f"{package!r} was refused"


@pytest.mark.parametrize("package", INVALID_PACKAGES)
def test_a_package_that_is_not_a_dotted_identifier_is_refused(package: str) -> None:
    with pytest.raises(ValidationError):
        target(package=package)


def test_a_folder_that_escapes_the_project_is_a_config_error_naming_the_key(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.rp-generate]\nschema = "m.yaml"\npackage = "p"\npython = "../out"\n'
    )
    with pytest.raises(ConfigError, match="python"):
        read_targets(tmp_path / "pyproject.toml", build_parser().parse_args([]))


# --- the manifest cannot make a run delete outside the project ---


@pytest.fixture
def generated(tmp_path: Path) -> tuple[Path, Path]:
    """A generated project inside ``tmp_path/proj``; returns its pyproject.toml and a file outside it."""
    home = tmp_path / "proj"
    home.mkdir()
    pyproject = project(home)
    assert main(["--project", str(pyproject)]) == 0, "the project must generate"
    victim = tmp_path / "outside" / "victim.txt"
    victim.parent.mkdir()
    victim.write_text("precious", encoding="utf-8")
    return pyproject, victim


def plant(pyproject: Path, *entries: ManifestEntry) -> None:
    """Add entries to the outputs of the manifest, bypassing the validation a reader applies."""
    recorded = read_manifest(pyproject)
    planted = GenerationManifest.model_construct(
        linkml=recorded.linkml, inputs=recorded.inputs, outputs=[*recorded.outputs, *entries]
    )
    (pyproject.parent / MANIFEST).write_text(planted.model_dump_json(), encoding="utf-8")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize(
    "path",
    ["../outside/victim.txt", "{victim}", "sub/../../outside/victim.txt", "C:/outside/victim.txt"],
    ids=["parent", "absolute", "buried-parent", "drive"],
)
def test_a_manifest_entry_outside_the_project_deletes_nothing_and_is_reported(
    generated: tuple[Path, Path], path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject, victim = generated
    plant(
        pyproject,
        ManifestEntry.model_construct(path=path.format(victim=victim), sha256=sha("precious")),
    )
    capsys.readouterr()
    assert main(["--project", str(pyproject)]) == 1, "an unusable manifest did not fail the run"
    assert victim.read_text() == "precious", "a file outside the project was deleted"
    assert "rp-manifest.json" in capsys.readouterr().err, "the unusable manifest was not named"


def test_an_entry_that_resolves_outside_through_a_link_is_kept_and_reported(
    generated: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject, victim = generated
    (pyproject.parent / "link").symlink_to(victim.parent)
    plant(pyproject, ManifestEntry(path="link/victim.txt", sha256=sha("precious")))
    capsys.readouterr()
    assert main(["--project", str(pyproject)]) == 1, "an escaping entry did not fail the run"
    assert victim.read_text() == "precious", "a file reached through a link was deleted"
    assert "outside the project" in capsys.readouterr().err, "the escape was not reported"


def test_a_listed_file_that_changed_since_it_was_generated_is_kept_and_reported(
    generated: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject, _ = generated
    stale = pyproject.parent / "app/generated/stale.py"
    stale.write_text("edited by hand", encoding="utf-8")
    plant(pyproject, ManifestEntry(path="app/generated/stale.py", sha256=sha("as generated")))
    capsys.readouterr()
    assert main(["--project", str(pyproject)]) == 1, "an edited stale output did not fail the run"
    assert stale.read_text() == "edited by hand", "an edited file was deleted"
    assert "stale.py" in capsys.readouterr().err, "the kept file was not named"


def test_a_listed_file_with_its_recorded_hash_is_deleted(generated: tuple[Path, Path]) -> None:
    pyproject, _ = generated
    stale = pyproject.parent / "app/generated/stale.py"
    stale.write_text("as generated", encoding="utf-8")
    plant(pyproject, ManifestEntry(path="app/generated/stale.py", sha256=sha("as generated")))
    assert main(["--project", str(pyproject)]) == 0, "the run failed"
    assert not stale.exists(), "a stale output with its recorded hash was kept"


# --- staged files stay in the staging folder ---


@pytest.fixture
def run(tmp_path: Path) -> Run:
    project(tmp_path)
    return Run(target(), tmp_path, tmp_path / "staging", load_schema(tmp_path / "m.yaml"))


@pytest.mark.parametrize("relative", ["../evil.py", "pkg/../../evil.py", "/evil.py"])
def test_a_staged_path_outside_the_staging_folder_is_a_step_error(run: Run, relative: str) -> None:
    with pytest.raises(StepError, match="staging"):
        run.staged(Path(relative))


@pytest.mark.parametrize("name", ["../evil.py", "a/b.py", "..", "", "a\\b.py", "."])
def test_an_output_name_that_is_not_a_plain_file_name_is_a_step_error(run: Run, name: str) -> None:
    with pytest.raises(StepError, match="file name"):
        stage(run, Path("pkg"), [GeneratedFile(name=name, text="x")])
    assert not (run.base / "evil.py").exists(), "a file was written outside the staging folder"


# --- exceptions: schema faults are reported, bugs surface ---


def test_a_schema_fault_raised_by_an_extension_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(_path: Path) -> list[GeneratedFile]:
        raise SchemaGenerationError("Thing: this schema asks for the impossible")

    monkeypatch.setattr(
        steps, "STEPS", (render_step("python", refuse, lambda run: run.python_dir),)
    )
    assert main(["--project", str(project(tmp_path))]) == 1, "a schema fault did not fail the run"
    assert "asks for the impossible" in capsys.readouterr().err, "the fault was not reported"


@pytest.mark.parametrize("bug", [KeyError("boom"), AttributeError("boom"), RuntimeError("boom")])
def test_a_bug_in_an_extension_is_not_reported_as_a_schema_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bug: Exception
) -> None:
    def crash(_path: Path) -> list[GeneratedFile]:
        raise bug

    monkeypatch.setattr(steps, "STEPS", (render_step("python", crash, lambda run: run.python_dir),))
    with pytest.raises(type(bug)):
        main(["--project", str(project(tmp_path))])


@pytest.mark.parametrize(
    "broken",
    [
        "a: [b\n",
        "id: x\nname: m\nclasses:\n  A:\n    nonsense: 1\n",
        "id: x\nname: m\nimports: [nope]\n",
        "",
    ],
    ids=["yaml", "unknown-field", "missing-import", "empty"],
)
def test_a_schema_that_does_not_load_is_reported_with_its_file(
    tmp_path: Path, broken: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--project", str(project(tmp_path, broken))]) == 1, "an unloadable schema passed"
    assert "m.yaml: load:" in capsys.readouterr().err, "the load problem was not reported"
