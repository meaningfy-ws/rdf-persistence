"""The consumer-term scan of docs/tools/check_docs.py catches a planted term (PD-20)."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_docs", Path(__file__).resolve().parents[2] / "docs/tools/check_docs.py"
)
assert _SPEC and _SPEC.loader
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

    assert found == {"rdf_persistence/a.py", "tests/b.yaml"}


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
    assert all("some_helper" in e for e in errors)
