"""docs/tools/reference.py writes the public API and the rp-generate usage, and --check fails on a
stale copy (documentation-improvements DEC-6)."""

import importlib.util
import types
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "reference", Path(__file__).resolve().parents[3] / "docs/tools/reference.py"
)
assert _SPEC, "the reference script was found"
assert _SPEC.loader, "the reference script has a loader"
reference = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference)


def test_the_api_table_has_a_row_per_name_with_its_first_sentence():
    module = types.ModuleType("pkg")

    class Widget:
        """A widget. More words follow here."""

    def make() -> None:
        """Make one."""

    module.Widget, module.make, module.LIMIT = Widget, make, 5
    module.__all__ = ["make", "Widget", "LIMIT"]

    table = reference.api_table(module)

    rows = [line for line in table.splitlines() if line.startswith("|`")]
    assert rows == [
        "|`LIMIT` |constant |",
        "|`make` |function |Make one.",
        "|`Widget` |class |A widget.",
    ], "one row per name, sorted without case, with its kind and first sentence"


def test_the_usage_is_the_parsers_help():
    assert "--check" in reference.cli_usage(), "the rp-generate options are listed"


def test_the_problem_table_has_every_kind_with_its_status_and_description():
    table = reference.problem_table()

    assert "|`key-conflict` |409 |Key conflict |" in table, "slug, status and title of a kind"
    assert "another aggregate of its class holds" in table, "the schema's description is shown"
    assert table.count("\n|`") == 17, "one row per kind of problem"


def test_check_fails_on_a_stale_partial_and_passes_once_written(tmp_path, monkeypatch):
    monkeypatch.setattr(reference, "PARTIALS", tmp_path)
    (tmp_path / "public-api.adoc").write_text("stale\n")

    assert reference.main(["--check"]) == 1, "a stale partial fails the check"
    assert reference.main([]) == 0, "writing succeeds"
    assert reference.main(["--check"]) == 0, "the written partials are fresh"
