"""Helpers the ``rp-uml2linkml`` command's tests share: a drawn library, a prefixes file, a run."""

from pathlib import Path

import pytest

from rdf_persistence_generation.uml.cli import main
from tests.generator.uml_qea import QeaBuilder

ROOT = "MODEL/library"
PREFIX = "rp-uml2linkml: "
PREFIXES = """\
schema_base: https://example.org/ns/library/
default_prefix: lib
version: "1"
prefixes:
  lib: https://example.org/ns/library#
  dct: http://purl.org/dc/terms/
"""


def build_library(tmp_path: Path) -> tuple[QeaBuilder, dict[str, int]]:
    builder = QeaBuilder(tmp_path / "library.qea")
    ids: dict[str, int] = {}
    ids["model"] = builder.package("MODEL")
    ids["library"] = builder.package("library", parent=ids["model"])
    ids["book"] = builder.cls(ids["library"], "lib:Book", stereotype="root", note="A book.")
    # every plain concrete class derives as a root, so a drawn «root» must be on all three (PD-6)
    ids["chapter"] = builder.cls(ids["library"], "lib:Chapter", stereotype="root")
    ids["folio"] = builder.cls(ids["library"], "lib:Folio", stereotype="root")
    return builder, ids


def prefixes_file(tmp_path: Path, text: str = PREFIXES) -> Path:
    path = tmp_path / "prefixes.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def run(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    qea: Path,
    *options: str,
    prefixes: Path | None = None,
    package: str = ROOT,
) -> tuple[int, list[str]]:
    """Run the command into ``tmp_path/out``; return the exit code and the stderr lines."""
    argv = [
        str(qea),
        "--package",
        package,
        "--prefixes",
        str(prefixes or prefixes_file(tmp_path)),
        "--out",
        str(tmp_path / "out"),
        *options,
    ]
    code = main(argv)
    return code, capsys.readouterr().err.splitlines()
