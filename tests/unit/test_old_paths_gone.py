"""No configuration, build or tooling file still names the generator's old path (TC-14c, PD-10).

The scan reads the files that a path list lives in; it leaves out ``openspec/``, the changelog, the
migration note of the adoption guide and the tests (a test may name the old path to prove it is gone).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OLD_FOLDER = "rdf_persistence/generation"
OLD_MODULE = "rdf_persistence.generation"
# the files where a path list, a coverage source, a lane or a CI step could still name the old folder
TOOLING = [
    "Makefile",
    "pyproject.toml",
    "pytest.ini",
    "ruff.toml",
    "mypy.ini",
    ".coveragerc",
    ".importlinter",
    ".pre-commit-config.yaml",
    "sonar-project.properties",
    ".gitignore",
    ".test_durations",
]
SOURCE_FOLDERS = ["rdf_persistence", "rdf_persistence_generation", ".github", "docs"]
MIGRATION_NOTE = "docs/modules/ROOT/pages/howto/adopt.adoc"


def files_to_scan() -> list[Path]:
    found = [ROOT / name for name in TOOLING if (ROOT / name).is_file()]
    for folder in SOURCE_FOLDERS:
        found += [
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.suffix not in {".pyc", ".png", ".svg", ".whl"}
            and p.relative_to(ROOT).as_posix() != MIGRATION_NOTE
        ]
    return sorted(found)


def test_no_tooling_or_source_file_names_the_old_generator_path() -> None:
    """Found: ``.test_durations`` still lists the old ``rdf_persistence/generation`` and ``tests/unit/generation`` ids."""
    hits = []
    for path in files_to_scan():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if OLD_FOLDER in line or OLD_MODULE in line:
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{number}")

    assert hits == [], f"{len(hits)} lines name the old path, first: {hits[:5]}"


@pytest.mark.parametrize("folder", ["tests/unit/generation", "rdf_persistence/generation"])
def test_the_old_folders_are_gone(folder: str) -> None:
    """TC-14c: neither the old source folder nor the old test folder holds a file."""
    left = [p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts]

    assert left == [], f"{folder} still holds {[p.name for p in left][:5]}"


def test_the_durations_file_names_only_tests_that_exist() -> None:
    """Found: the shard balancer's file lists test ids of files that were moved or deleted."""
    durations = json.loads((ROOT / ".test_durations").read_text(encoding="utf-8"))
    files = {key.split("::")[0] for key in durations}

    missing = sorted(f for f in files if not (ROOT / f).is_file())
    assert missing == [], (
        f"{len(missing)} files in .test_durations do not exist, first: {missing[:5]}"
    )


def test_importing_the_removed_generator_package_is_a_module_not_found_error() -> None:
    """Error matrix (DEC-5): ``import rdf_persistence.generation`` fails naming the missing module."""
    code = (
        "import json\n"
        "try:\n"
        "    import rdf_persistence.generation\n"
        "except ModuleNotFoundError as error:\n"
        "    print(json.dumps(error.name))\n"
    )

    done = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.splitlines()[-1]) == "rdf_persistence.generation", (
        "the old generator package still imports, or fails for another reason"
    )
