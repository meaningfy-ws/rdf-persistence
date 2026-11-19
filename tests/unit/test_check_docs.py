"""The checks of docs/tools/check_docs.py: consumer terms (PD-20), the testkit names, the mermaid
pin and every link resolving to a page and an anchor (documentation-improvements DEC-7)."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_docs", Path(__file__).resolve().parents[2] / "docs/tools/check_docs.py"
)
assert _SPEC, "the check script was found"
assert _SPEC.loader, "the check script has a loader"
check_docs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_docs)

# Built from parts so this file does not trip the scan itself.
_TERM = "M" + "WB"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"see the {_TERM} adapter", 1),
        (f"{_TERM}2 is a different word", 0),
        ("a toy library book", 0),
    ],
)
def test_forbidden_in_reports_whole_word_terms(tmp_path, monkeypatch, text, expected):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    planted = tmp_path / "rdf_persistence" / "planted.py"
    planted.parent.mkdir()
    planted.write_text(text)

    errors = check_docs.forbidden_in([planted])

    assert len(errors) == expected, errors


def test_code_files_scans_the_package_and_the_tests(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    for rel in ["rdf_persistence/a.py", "tests/b.yaml", "tests/__pycache__/c.py", "docs/d.py"]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("")

    found = {f.relative_to(tmp_path).as_posix() for f in check_docs.code_files()}

    assert found == {"rdf_persistence/a.py", "tests/b.yaml"}, (
        "both the package and the test files are found"
    )


def _testkit_with_page(tmp_path, monkeypatch, page_text):
    """A tmp repo whose testkit exports `exported`, plus a testing page with `page_text`."""
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    monkeypatch.setattr(check_docs, "MODULE", tmp_path / "docs")
    testkit = tmp_path / "rdf_persistence" / "testkit"
    (testkit / "containers").mkdir(parents=True)
    (testkit / "__init__.py").write_text('__all__ = ["exported"]\n')
    (testkit / "containers" / "__init__.py").write_text("")
    (testkit / "bootstrap.py").write_text("")
    page = tmp_path / "docs" / "pages" / "develop" / "testing.adoc"
    page.parent.mkdir(parents=True)
    page.write_text(page_text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("use `testkit.exported`", 0),
        ("use `testkit.some_helper`", 1),
        ("see `testkit.containers.fixtures`", 0),
        ("see `testkit.bootstrap`", 0),
    ],
)
def test_testkit_names_must_be_exported_or_a_submodule(tmp_path, monkeypatch, text, expected):
    _testkit_with_page(tmp_path, monkeypatch, text)

    errors = check_docs.check_testkit_names()

    assert len(errors) == expected, errors
    assert all("some_helper" in e for e in errors), "each error names the helper"


def test_a_testkit_without_all_is_reported_as_such_not_as_every_name_unexported(
    tmp_path, monkeypatch
):
    _testkit_with_page(tmp_path, monkeypatch, "use `testkit.exported` and `testkit.other`")
    (tmp_path / "rdf_persistence/testkit/__init__.py").write_text("")

    errors = check_docs.check_testkit_names()

    assert len(errors) == 1, errors
    assert "__all__" in errors[0], "the error says there is no __all__"
    assert "not exported" not in errors[0], "the error does not say names are unexported"


def _repo_with_pin(tmp_path, monkeypatch, pinned: str, served: list[str]):
    """A tmp repo whose Makefile pins `pinned` and whose playbooks serve the `served` versions."""
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    (tmp_path / "Makefile").write_text(f"MERMAID_VERSION = {pinned}\n")
    (tmp_path / "docs").mkdir()
    for i, version in enumerate(served):
        url = f"https://cdn.jsdelivr.net/npm/mermaid@{version}/dist/mermaid.esm.min.mjs"
        (tmp_path / "docs" / f"antora-playbook{i}.yml").write_text(f"mermaid_library_url: {url}\n")


def test_playbooks_serving_the_pinned_mermaid_pass(tmp_path, monkeypatch):
    _repo_with_pin(tmp_path, monkeypatch, "12.3.0", ["12.3.0", "12.3.0"])

    assert check_docs.check_mermaid_pin() == [], "pinned playbooks pass"


@pytest.mark.parametrize("other", ["10", "12.3.1", "12"])
def test_a_playbook_serving_another_mermaid_fails(tmp_path, monkeypatch, other):
    _repo_with_pin(tmp_path, monkeypatch, "12.3.0", ["12.3.0", other])

    assert len(check_docs.check_mermaid_pin()) == 1, "exactly one playbook is reported"


def test_a_makefile_without_a_mermaid_pin_fails(tmp_path, monkeypatch):
    _repo_with_pin(tmp_path, monkeypatch, "12.3.0", ["12.3.0"])
    (tmp_path / "Makefile").write_text("all:\n")

    assert check_docs.check_mermaid_pin() == ["Makefile: no MERMAID_VERSION"], (
        "a Makefile with no pin is reported"
    )


def test_mermaid_markdown_holds_every_block_of_every_page(tmp_path, monkeypatch):
    monkeypatch.setattr(check_docs, "MODULE", tmp_path)
    page = tmp_path / "pages" / "a.adoc"
    page.parent.mkdir(parents=True)
    page.write_text(
        "= A\n\n[mermaid]\n....\nflowchart LR\n  X --> Y\n....\n\ntext\n\n"
        "[mermaid]\n....\nsequenceDiagram\n  A->>B: hi\n....\n"
    )

    markdown = check_docs.mermaid_markdown()

    assert markdown.count("```mermaid\n") == 2, "both mermaid blocks are in the markdown"
    assert "flowchart LR\n  X --> Y\n```" in markdown, "the flowchart block is in the markdown"
    assert "sequenceDiagram\n  A->>B: hi\n```" in markdown, "the sequence block is in the markdown"


def _site(tmp_path, monkeypatch, pages: dict[str, str], nav: str = "") -> None:
    """A tmp docs module with the given pages (path -> text) and nav."""
    monkeypatch.setattr(check_docs, "MODULE", tmp_path)
    for path, text in pages.items():
        (tmp_path / "pages" / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "pages" / path).write_text(text)
    (tmp_path / "nav.adoc").write_text(nav)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Where things are", "where-things-are"),
        ("1. Install", "1-install"),
        ("The `Session` and its *unit* of work", "the-session-and-its-unit-of-work"),
        ("Errors: what a caller sees!", "errors-what-a-caller-sees"),
        ("Moving from the old keywords (0.4)", "moving-from-the-old-keywords-0-4"),
    ],
)
def test_section_ids_follow_the_site_settings(title, expected):
    assert check_docs.section_id(title) == expected, "the id the site (idseparator '-') gives"


def test_section_ids_follow_asciidoctor_defaults():
    assert check_docs.section_id("1. Install", "_", "_") == "_1_install", "Asciidoctor's default"


def test_resolving_links_pass(tmp_path, monkeypatch):
    _site(
        tmp_path,
        monkeypatch,
        {
            "a.adoc": "= A\n\n[#here]\n== Here\n\n"
            "See <<here>>, <<more,more>> and xref:b.adoc#two[two].\n\n== More\n",
            "b.adoc": "= B\n:page-aliases: old/b.adoc\n\n== Two\n\n"
            "[[pin]]text xref:old/b.adoc#pin[] xref:ROOT:a.adoc[]\n",
        },
        nav="* xref:a.adoc[A]\n* xref:b.adoc#two[B]\n",
    )

    assert check_docs.check_links() == [], "every link resolves"


def test_an_explicit_id_replaces_the_title_id(tmp_path, monkeypatch):
    _site(tmp_path, monkeypatch, {"a.adoc": "= A\n\n[#here]\n== Over there\n\n<<over-there>>\n"})

    assert len(check_docs.check_links()) == 1, "the title's own id is not defined"


def test_repeated_titles_get_numbered_ids(tmp_path, monkeypatch):
    _site(tmp_path, monkeypatch, {"a.adoc": "= A\n\n== Limits\n\n== Limits\n\n<<limits-2>>\n"})

    assert check_docs.check_links() == [], "the second title's id ends in -2"


@pytest.mark.parametrize(
    ("text", "missing"),
    [
        ("xref:nowhere.adoc[x]", "nowhere.adoc"),
        ("xref:b.adoc#gone[x]", "b.adoc#gone"),
        ("<<gone>>", "gone"),
        ("<<b.adoc#gone,x>>", "b.adoc#gone"),
    ],
)
def test_a_broken_link_is_reported(tmp_path, monkeypatch, text, missing):
    _site(tmp_path, monkeypatch, {"a.adoc": f"= A\n\n{text}\n", "b.adoc": "= B\n\n== Two\n"})

    errors = check_docs.check_links()

    assert len(errors) == 1, errors
    assert "a.adoc" in errors[0] and missing in errors[0], "the page and the target are named"


def test_a_broken_link_in_the_nav_is_reported(tmp_path, monkeypatch):
    _site(tmp_path, monkeypatch, {"a.adoc": "= A\n"}, nav="* xref:a.adoc#nope[A]\n")

    errors = check_docs.check_links()

    assert len(errors) == 1 and "nav.adoc" in errors[0], errors


def test_links_in_listings_and_comments_are_ignored(tmp_path, monkeypatch):
    page = "= A\n\n----\nxref:x.adoc[] <<y>>\n----\n\n// xref:z.adoc[]\n\n....\n<<w>>\n....\n"
    _site(tmp_path, monkeypatch, {"a.adoc": page})

    assert check_docs.check_links() == [], "verbatim blocks and comments are not links"
