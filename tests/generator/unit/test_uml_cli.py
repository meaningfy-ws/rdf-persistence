"""TC-10: the ``rp-uml2linkml`` command's usage errors and model problems (PD-1, PD-5, PD-22, PD-23).

What the command writes on success (exit 0, the converter's own problems) is the golden's and IT-1's.
"""

from pathlib import Path

import pytest

from rdf_persistence_generation.generated.rp_generation import UmlSettings
from rdf_persistence_generation.uml.cli import load_settings, main
from rdf_persistence_generation.uml.toolkit import load_toolkit
from tests.generator.uml_qea import QeaBuilder

from . import uml_cli_breaches as breaches
from .uml_cli_run import (
    PREFIX,
    PREFIXES,
    ROOT,
    build_library,
    noted_library,
    prefixes_file,
    run,
    run_check,
)


def snapshot(folder: Path) -> dict[str, bytes]:
    return {file.name: file.read_bytes() for file in sorted(folder.iterdir())}


# --- the model problems of the reader (TC-10) ---------------------------------------------------


def test_three_faults_give_three_sorted_lines_exit_one_and_leave_out_unchanged(tmp_path, capsys):
    builder, ids = build_library(tmp_path)
    # a class to class Realisation: the reader has no geometry fault left, so this is the third one
    builder.realisation(ids["book"], ids["chapter"])
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


def test_a_roles_file_the_loader_refuses_exits_one_with_its_message_and_writes_nothing(
    tmp_path, capsys, monkeypatch
):
    from rdf_persistence.core.domain.exceptions import InvalidRoleDefinition
    from rdf_persistence_generation.uml import write as write_module

    def refuse(path):
        raise InvalidRoleDefinition("entry 1: refused")

    monkeypatch.setattr(write_module, "load_role_definitions", refuse)  # X3
    builder, ids = build_library(tmp_path)
    role_definition = builder.cls(ids["library"], "rp:RoleDefinition")
    builder.object_(
        ids["library"],
        "reader",
        role_definition,
        "".join(
            f"@VAR;Variable={name};Value={value};Op==;@ENDVAR;"
            for name, value in (("role", "reader"), ("level", "tenant"), ("actions", "read"))
        ),
    )

    toolkit = prefixes_file(tmp_path, PREFIXES + "  rp: https://meaningfy.ws/ns/rdf-persistence#\n")

    code, lines = run(capsys, tmp_path, builder.finish(), prefixes=toolkit)

    assert (code, lines) == (1, [f"{PREFIX}entry 1: refused"]), (code, lines)
    assert not any((tmp_path / "out").glob("*")), "nothing is moved into out"


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


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        pytest.param(
            "schema_base: https://example.org/ns/library/",
            "schema_base: example.org/ns/library/",
            "schema_base example.org/ns/library/ is not an absolute IRI",
            id="schema_base",
        ),
        pytest.param(
            "  lib: https://example.org/ns/library#",
            "  lib: example.org/ns/library#",
            "namespace example.org/ns/library# of prefix lib is not an absolute IRI",
            id="namespace",
        ),
        pytest.param(
            "  dct: http://purl.org/dc/terms/",
            "  1dct: http://purl.org/dc/terms/",
            "prefix 1dct is not an NCName",
            id="prefix-name",
        ),
        pytest.param(
            "default_prefix: lib",
            "default_prefix: other",
            "default_prefix other is not a key of prefixes",
            id="default-prefix",
        ),
    ],
)
def test_a_prefixes_value_that_is_unusable_is_a_usage_error(tmp_path, capsys, old, new, message):
    builder, _ = build_library(tmp_path)
    assert old in PREFIXES, f"the fixture must hold {old!r}"
    broken = prefixes_file(tmp_path, PREFIXES.replace(old, new))

    code, lines = run(capsys, tmp_path, builder.finish(), prefixes=broken)

    assert (code, lines) == (2, [f"{PREFIX}{broken}: {message}"]), (code, lines)
    assert not (tmp_path / "out").exists(), "nothing is written"


def test_a_root_name_that_is_not_an_ncname_is_a_usage_error(tmp_path, capsys):
    builder, _ = build_library(tmp_path)

    code, lines = run(capsys, tmp_path, builder.finish(), "--root-name", "my app")

    assert (code, lines) == (2, [f"{PREFIX}--root-name my app is not an NCName"]), (code, lines)
    assert not (tmp_path / "out").exists(), "nothing is written"


def test_a_file_that_is_not_sqlite_is_a_usage_error(tmp_path, capsys):
    text = tmp_path / "model.qea"
    text.write_text("this is not a database, and it is long enough to look like a header\n" * 8)

    code, lines = run(capsys, tmp_path, text)

    assert (code, lines) == (
        2,
        [f"{PREFIX}{text} is not an Enterprise Architect .qea (SQLite) file"],
    ), (code, lines)


def test_an_unwritable_out_is_a_usage_error(tmp_path, capsys):
    builder, _ = build_library(tmp_path)
    out = tmp_path / "out"
    out.write_text("not a folder", encoding="utf-8")

    code, lines = run(capsys, tmp_path, builder.finish())

    assert (code, lines) == (2, [f"{PREFIX}cannot write {out}: File exists"]), (code, lines)


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
    prefixes = load_toolkit().prefixes()

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


# --- --check (PD-14, PD-13) ---------------------------------------------------------------------


def test_check_on_a_model_with_a_problem_exits_one_and_leaves_a_filled_out_identical(
    tmp_path, capsys
):
    builder = QeaBuilder(tmp_path / "empty.qea")
    builder.package("library", parent=builder.package("MODEL"))
    out = tmp_path / "out"
    out.mkdir()
    (out / "app.uml-report.txt").write_text("kept\n", encoding="utf-8")
    before = snapshot(out)

    code, stdout, stderr = run_check(capsys, tmp_path, builder.finish(), out=out)

    assert code == 1, "a problem exits 1"
    assert len(stderr) == 1, f"the problem is printed on stderr: {stderr}"
    assert not stdout, f"no convention line without a converted model: {stdout}"
    assert snapshot(out) == before, "--check rewrites no report and writes nothing"


def test_check_with_only_a_convention_line_prints_it_to_stdout_and_exits_one(tmp_path, capsys):
    builder, _ = build_library(tmp_path)  # Chapter and Folio carry no note

    code, stdout, stderr = run_check(capsys, tmp_path, builder.finish())

    assert code == 1, "a convention line fails the check"
    assert not stderr, f"nothing on stderr: {stderr}"
    assert len(stdout) == 2, f"one no-note line per noteless class: {stdout}"
    assert all(len(line.split("\t")) == 3 for line in stdout), f"report format: {stdout}"
    assert all(line.startswith("no-note\t") for line in stdout), f"kind no-note: {stdout}"
    assert stdout == sorted(stdout), "the lines are sorted"


@pytest.mark.parametrize("stereotype", [None, "root"], ids=["no stereotype", "agreeing root"])
def test_check_on_a_clean_model_exits_zero_prints_nothing_and_needs_no_out(
    tmp_path, capsys, stereotype
):
    builder, _ = noted_library(tmp_path, stereotype)

    code, stdout, stderr = run_check(capsys, tmp_path, builder.finish())

    assert code == 0, f"a clean model, or one with only an agreeing root, passes: {stdout}"
    assert not stdout, f"nothing on stdout: {stdout}"
    assert not stderr, f"nothing on stderr: {stderr}"
    assert not (tmp_path / "out").exists(), "--check writes nothing"


def test_check_with_an_out_still_writes_nothing(tmp_path, capsys):
    builder, _ = noted_library(tmp_path, None)
    out = tmp_path / "given"

    code, _, _ = run_check(capsys, tmp_path, builder.finish(), out=out)

    assert code == 0, "the clean model passes"
    assert not out.exists(), "--out is accepted under --check and not written"


def test_a_run_without_check_and_without_out_exits_two(tmp_path, capsys):
    builder, _ = noted_library(tmp_path)
    argv = [str(builder.finish()), "--package", ROOT, "--prefixes", str(prefixes_file(tmp_path))]

    code = main(argv)

    assert code == 2, "--out is required unless --check is given"
    assert capsys.readouterr().err.startswith(PREFIX), "one usage line with the program name"


def test_a_normal_run_with_a_convention_line_exits_zero_and_writes(tmp_path, capsys):
    builder, _ = build_library(tmp_path)

    code, lines = run(capsys, tmp_path, builder.finish())

    assert (code, lines) == (0, []), f"a convention line never fails a normal run: {lines}"
    report = (tmp_path / "out" / "app.uml-report.txt").read_text(encoding="utf-8")
    assert "no-note\t" in report, "the line is in the report"


# --- each convention fails the check (PD-13, D-14, Q9) --------------------------------------------
# A convention line is printed on stdout in the report format, a problem on stderr as ``[rule] ...``.

LINE, PROBLEM = "line", "problem"
BREACHES = [
    ("unprefixed-name", breaches.unprefixed_class, None, LINE, "unprefixed-name", "Shelf"),
    (
        "unspecified-multiplicity",
        breaches.no_multiplicity,
        None,
        LINE,
        "unspecified-multiplicity",
        "Book.has_folio",
    ),
    ("no-note", breaches.no_note, None, LINE, "no-note", "Shelf"),
    ("root_class", breaches.part_drawn_root, "root", PROBLEM, "root_class", "Chapter"),
    ("unused-enumeration", breaches.unused_enumeration, None, LINE, "unused-enumeration", "Genre"),
    (
        "package_module",
        breaches.two_packages_one_module,
        None,
        PROBLEM,
        "package_module",
        "app_rare_books",
    ),
    (
        "boundary_owned role",
        breaches.role_owned_and_pointer,
        None,
        PROBLEM,
        "boundary_owned",
        "has_chapter",
    ),
    (
        "boundary_owned part",
        breaches.pointer_into_a_part,
        None,
        PROBLEM,
        "boundary_owned",
        "Folio.cites",
    ),
    (
        "drawn-toolkit-parent",
        breaches.drawn_toolkit_parent,
        None,
        LINE,
        "drawn-toolkit-parent",
        "Book",
    ),
    (
        "tenant-required-pointer",
        breaches.tenant_required_pointer,
        None,
        LINE,
        "tenant-required-pointer",
        "Library.holds",
    ),
    (
        "boundary-disagrees",
        breaches.boundary_for_a_part,
        None,
        LINE,
        "boundary-disagrees",
        "Aggregate: Chapter",
    ),
]


@pytest.mark.parametrize(
    ("seed", "stereotype", "stream", "kind", "element"),
    [row[1:] for row in BREACHES],
    ids=[row[0] for row in BREACHES],
)
def test_each_convention_fails_the_check(tmp_path, capsys, seed, stereotype, stream, kind, element):
    builder, ids = noted_library(tmp_path, stereotype)
    seed(builder, ids)

    code, stdout, stderr = run_check(
        capsys, tmp_path, builder.finish(), prefixes=PREFIXES + breaches.TOOLKIT_PREFIX
    )

    printed, other = (stdout, stderr) if stream == LINE else (stderr, stdout)
    assert code == 1, f"{kind} fails the check: {stdout} {stderr}"
    assert len(printed) == 1, f"exactly one {stream}, the breach: {printed}"
    assert kind in printed[0], f"it is a {kind} {stream}: {printed}"
    assert element in printed[0], f"it names {element}: {printed}"
    assert not other, f"nothing on the other stream: {other}"


def test_a_reader_problem_short_circuits_check_and_is_the_only_output(tmp_path, capsys):
    builder, ids = build_library(tmp_path)  # the noteless classes would give convention lines
    builder.realisation(ids["book"], ids["chapter"])

    code, stdout, stderr = run_check(capsys, tmp_path, builder.finish())

    assert code == 1, "a reader problem exits 1"
    assert len(stderr) == 1, f"the problem only: {stderr}"
    assert stderr[0].startswith("[no_rule] "), f"it is the reader's: {stderr}"
    assert not stdout, f"the convention lines wait until it is fixed (A-21): {stdout}"
