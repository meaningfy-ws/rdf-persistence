"""TC-10: the ``rp-uml2linkml`` command's usage errors and model problems (PD-1, PD-5, PD-22, PD-23).

What the command writes on success (exit 0, the converter's own problems) is the golden's and IT-1's.
"""

from pathlib import Path

import pytest

from rdf_persistence_generation.generated.rp_generation import UmlSettings
from rdf_persistence_generation.uml.cli import load_settings, main, metamodel_prefixes
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
BOX = (-20, 30, 320, -298)  # (left, top, right, bottom)
INSIDE = (0, 0, 100, -50)
STRADDLING = (300, 0, 400, -50)


def build_library(tmp_path: Path) -> tuple[QeaBuilder, dict[str, int]]:
    builder = QeaBuilder(tmp_path / "library.qea")
    ids: dict[str, int] = {}
    ids["model"] = builder.package("MODEL")
    ids["library"] = builder.package("library", parent=ids["model"])
    ids["book"] = builder.cls(ids["library"], "lib:Book", stereotype="root", note="A book.")
    ids["chapter"] = builder.cls(ids["library"], "lib:Chapter")
    ids["folio"] = builder.cls(ids["library"], "lib:Folio")
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


def snapshot(folder: Path) -> dict[str, bytes]:
    return {file.name: file.read_bytes() for file in sorted(folder.iterdir())}


# --- the model problems of the reader (TC-10) ---------------------------------------------------


def test_three_faults_give_three_sorted_lines_exit_one_and_leave_out_unchanged(tmp_path, capsys):
    builder, ids = build_library(tmp_path)
    builder.boundary(diagram=1, rect=BOX, members=[])
    builder.place(1, ids["book"], INSIDE)
    builder.place(1, ids["chapter"], STRADDLING)  # a straddling class
    builder.association(ids["book"], ids["folio"], role="lib:y", card="1", pdata1=str(ids["book"]))
    builder.extra_stereotypes(ids["folio"], "root", "loaded graph")  # a second stereotype
    out = tmp_path / "out"
    out.mkdir()
    (out / "lib_main.yaml").write_text("kept: yes\n", encoding="utf-8")
    before = snapshot(out)

    code, lines = run(capsys, tmp_path, builder.finish())

    assert code == 1, "model problems exit 1"
    assert len(lines) == 3, f"three problems are printed: {lines}"
    assert lines == sorted(lines), "the problems are printed sorted"
    assert all(line.startswith("[no_rule] ") for line in lines), f"all are no_rule: {lines}"
    assert snapshot(out) == before, "a failed run leaves the out folder as it was"


def test_the_path_form_and_the_name_form_of_the_package_write_the_same_files(tmp_path, capsys):
    builder, _ = build_library(tmp_path)
    qea = builder.finish()

    by_path = run(capsys, tmp_path, qea, package=ROOT)
    path_files = snapshot(tmp_path / "out")
    (tmp_path / "out" / "app.yaml").unlink()
    by_name = run(capsys, tmp_path, qea, package="library")

    assert by_path == by_name == (0, []), f"both forms exit 0 silently: {by_path}, {by_name}"
    assert "app_main.yaml" in path_files, f"the main module is written: {sorted(path_files)}"
    assert snapshot(tmp_path / "out") == path_files, "the name form writes the same files"


def test_a_package_with_no_class_or_enumeration_exits_one_and_writes_nothing(tmp_path, capsys):
    builder = QeaBuilder(tmp_path / "empty.qea")
    builder.package("library", parent=builder.package("MODEL"))

    code, lines = run(capsys, tmp_path, builder.finish())

    assert code == 1, "an empty package exits 1"
    assert lines == [
        f"[package_module] {ROOT}: the package holds no class or enumeration to convert"
    ], f"the problem is named: {lines}"
    assert not (tmp_path / "out").exists(), "nothing is written"


def test_an_out_folder_that_does_not_exist_is_not_created_by_a_failed_run(tmp_path, capsys):
    builder, ids = build_library(tmp_path)
    builder.extra_stereotypes(ids["book"], "root", "loaded graph")

    code, _ = run(capsys, tmp_path, builder.finish())

    assert code == 1, "model problems exit 1"
    assert not (tmp_path / "out").exists(), "a failed run does not create the out folder"


# --- the usage errors (exit 2): one line, prefixed -----------------------------------------------


def test_a_prefixes_file_without_a_key_is_a_usage_error(tmp_path, capsys):
    builder, _ = build_library(tmp_path)
    broken = prefixes_file(tmp_path, PREFIXES.replace("default_prefix: lib\n", ""))

    code, lines = run(capsys, tmp_path, builder.finish(), prefixes=broken)

    assert (code, lines) == (2, [f"{PREFIX}{broken}: missing default_prefix"]), (code, lines)


def test_a_prefixes_file_that_is_not_a_mapping_is_a_usage_error(tmp_path, capsys):
    builder, _ = build_library(tmp_path)
    broken = prefixes_file(tmp_path, "- one\n- two\n")

    code, lines = run(capsys, tmp_path, builder.finish(), prefixes=broken)

    assert (code, lines) == (2, [f"{PREFIX}{broken}: not a mapping"]), (code, lines)


def test_a_prefixes_entry_that_is_not_a_mapping_is_a_usage_error(tmp_path, capsys):
    builder, _ = build_library(tmp_path)
    broken = prefixes_file(tmp_path, PREFIXES.split("prefixes:")[0] + "prefixes: [lib]\n")

    code, lines = run(capsys, tmp_path, builder.finish(), prefixes=broken)

    assert (code, lines) == (2, [f"{PREFIX}{broken}: prefixes is not a mapping"]), (code, lines)


def test_a_file_that_is_not_sqlite_is_a_usage_error(tmp_path, capsys):
    text = tmp_path / "model.qea"
    text.write_text("this is not a database, and it is long enough to look like a header\n" * 8)

    code, lines = run(capsys, tmp_path, text)

    assert (code, lines) == (
        2,
        [f"{PREFIX}{text} is not an Enterprise Architect .qea (SQLite) file"],
    ), (code, lines)


def test_an_unknown_package_is_a_usage_error(tmp_path, capsys):
    builder, _ = build_library(tmp_path)

    code, lines = run(capsys, tmp_path, builder.finish(), package="nothing")

    assert (code, lines) == (2, [f"{PREFIX}no package nothing"]), (code, lines)


def test_an_exclude_package_that_matches_nothing_is_a_usage_error(tmp_path, capsys):
    builder, _ = build_library(tmp_path)

    code, lines = run(
        capsys, tmp_path, builder.finish(), "--exclude-package", "MODEL/library/nowhere"
    )

    assert (code, lines) == (
        2,
        [f"{PREFIX}no package MODEL/library/nowhere under library"],
    ), (code, lines)


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    assert exit_info.value.code == 0, "--help exits 0"
    assert "--prefixes" in capsys.readouterr().out, "the help names the --prefixes option"


# --- the prefixes file becomes settings (PD-5, P-0007) -----------------------------------------


def test_the_prefixes_file_and_the_options_become_settings(tmp_path):
    from rdf_persistence_generation.uml.cli import build_parser

    args = build_parser().parse_args(
        [
            "m.qea",
            "--package",
            ROOT,
            "--prefixes",
            "p.yaml",
            "--out",
            "o",
            "--exclude-package",
            "MODEL/library/x",
            "--not-generated",
            "legend",
        ]
    )

    settings = load_settings(prefixes_file(tmp_path), args)

    assert isinstance(settings, UmlSettings), "the settings are a UmlSettings"
    assert (settings.schema_base, settings.default_prefix, settings.schema_version) == (
        "https://example.org/ns/library/",
        "lib",
        "1",
    ), "the file's base, default prefix and version are read"
    assert [(p.prefix_name, p.namespace) for p in settings.prefixes or []] == [
        ("lib", "https://example.org/ns/library#"),
        ("dct", "http://purl.org/dc/terms/"),
    ], "the prefixes keep the file's order"
    assert settings.subtree_package == ROOT, "--package is the subtree"
    assert settings.root_name == "app", "the root name defaults to app"
    assert settings.exclude_packages == ["MODEL/library/x"], "--exclude-package is read"
    assert settings.default_mixins == ["Described", "Tracked"], "the mixins default"
    assert settings.not_generated_stereotypes == ["legend"], "--not-generated replaces the default"


def test_the_metamodel_prefixes_name_the_toolkit_namespaces():
    prefixes = metamodel_prefixes()

    assert prefixes["dcterms"] == "http://purl.org/dc/terms/", "dcterms is Dublin Core terms"
    assert prefixes["prov"] == "http://www.w3.org/ns/prov#", "prov is PROV-O"
    assert prefixes["rp"] == "https://meaningfy.ws/ns/rdf-persistence#", "rp is the toolkit's"


def test_the_defaults_are_the_documented_ones(tmp_path):
    from rdf_persistence_generation.uml.cli import build_parser

    args = build_parser().parse_args(
        ["m.qea", "--package", ROOT, "--prefixes", "p.yaml", "--out", "o"]
    )

    settings = load_settings(prefixes_file(tmp_path), args)

    assert settings.not_generated_stereotypes == ["loaded graph"], "loaded graph is not generated"
    assert not settings.exclude_packages, "nothing is excluded by default"
