"""Helpers the generation features share: a copy of the toy library, an edit of a copied file, one ``rp-generate`` run."""

import shutil
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main

TOY = Path(__file__).parents[2] / "fixtures" / "library"
IGNORED = shutil.ignore_patterns("__pycache__", "generated", "web")


def copy_toy(folder: Path) -> None:
    shutil.copytree(TOY, folder, ignore=IGNORED)


def generate(project: Path, capsys: pytest.CaptureFixture[str], *flags: str) -> tuple[int, str]:
    capsys.readouterr()
    code = main(["--project", str(project), *flags])
    return code, capsys.readouterr().err


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {path.name}: the edit would change nothing"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def tree(folder: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()
    }
