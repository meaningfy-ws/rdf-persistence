"""A toolkit copy an earlier run wrote is removed once the toolkit has its owner (typescript-toolkit-modules PD-7).

Before an entry sets `toolkit-typescript`, the one TypeScript target writes the toolkit's shared modules
(`rp_core.ts`, ...) next to its own classes. When the toolkit gets its owner, the next run removes that
copy through the manifest, with no code of its own.
"""

import shutil
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main

TOY = Path(__file__).parents[2] / "fixtures" / "library"
DOMAIN_TYPESCRIPT = 'typescript = "web/src/domain/generated"\n'
DOMAIN_OWNER = "toolkit-typescript = true\n"
TECHNICAL_TYPESCRIPT = 'typescript = "web/src/services/generated"\n'
COPY = Path("web/src/domain/generated/values/rp_core.ts")
OWNED = Path("web/src/domain/generated/values/loan_checks.ts")


@pytest.mark.slow
def test_the_old_toolkit_copy_is_removed_once_the_toolkit_has_an_owner(tmp_path: Path) -> None:
    project = tmp_path / "library"
    shutil.copytree(
        TOY, project, ignore=shutil.ignore_patterns("__pycache__", "generated", "golden", "web")
    )
    pyproject = project / "pyproject.toml"
    original = pyproject.read_text(encoding="utf-8")
    for line in (DOMAIN_TYPESCRIPT, DOMAIN_OWNER, TECHNICAL_TYPESCRIPT):
        assert line in original, f"the toy must carry {line.strip()!r}: nothing to take away"

    earlier = original
    for line in (DOMAIN_TYPESCRIPT, DOMAIN_OWNER, TECHNICAL_TYPESCRIPT):
        earlier = earlier.replace(line, "", 1)
    pyproject.write_text(earlier, encoding="utf-8")
    assert main(["--project", str(pyproject)]) == 0, "the earlier run must generate"
    assert (project / COPY).is_file(), (
        "the earlier run must write the toolkit copy, or the test is vacuous"
    )

    pyproject.write_text(original, encoding="utf-8")
    assert main(["--project", str(pyproject)]) == 0, "the later run must generate"
    assert not (project / COPY).exists(), "the toolkit copy of the earlier run must be removed"
    assert (project / OWNED).is_file(), "the value target must still write its own TypeScript"
