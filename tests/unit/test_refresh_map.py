"""The scenario-map refresher drops rows of vanished tests and lists unmapped ids (PD-16)."""

from pathlib import Path

import pytest

from tests.audit.refresh_map import (
    EXIT_COLLECTION_FAILED,
    EXIT_MALFORMED_MAP,
    EXIT_NEW_IDS,
    EXIT_OK,
    EXIT_REFUSED,
    function_ids,
    main,
    refresh,
)

HEADER = "test,level,capability,requirement,scenario,confidence,evidence"
KEPT_FIRST = "tests/unit/test_a.py::test_kept_first,scenario,cap,Req A,sc,high,name"
GONE = "tests/unit/test_a.py::test_gone,requirement,cap,Req B,,high,name"
KEPT_LAST = 'tests/unit/test_b.py::test_param,scenario,cap,Req C,sc,high,"name; code (x, y)"'
COLLECTED = """\
tests/unit/test_a.py::test_kept_first
tests/unit/test_b.py::test_param[one]
tests/unit/test_b.py::test_param[two-2]
tests/unit/test_b.py::TestKlass::test_new

3 tests collected in 0.10s
"""


def _map_text(*rows: str) -> str:
    return "\n".join((HEADER, *rows)) + "\n"


def test_a_parametrised_id_collapses_to_its_function() -> None:
    ids = function_ids(COLLECTED)

    assert ids == {
        "tests/unit/test_a.py::test_kept_first",
        "tests/unit/test_b.py::test_param",
        "tests/unit/test_b.py::TestKlass::test_new",
    }, "case suffixes and non-node lines must not leave the id set"


def test_refresh_removes_vanished_rows_and_keeps_the_rest_in_order() -> None:
    result = refresh(_map_text(KEPT_FIRST, GONE, KEPT_LAST), function_ids(COLLECTED))

    assert result.removed == ["tests/unit/test_a.py::test_gone"], "the vanished row is reported"
    assert result.text == _map_text(KEPT_FIRST, KEPT_LAST), (
        "kept rows are unchanged, quoting included, and in their order"
    )


def test_refresh_lists_collected_ids_that_have_no_row() -> None:
    result = refresh(_map_text(KEPT_FIRST, GONE, KEPT_LAST), function_ids(COLLECTED))

    assert result.new == ["tests/unit/test_b.py::TestKlass::test_new"], "unmapped id is reported"


def test_refresh_of_a_complete_map_changes_nothing() -> None:
    text = _map_text(KEPT_FIRST, KEPT_LAST)

    result = refresh(
        text, {"tests/unit/test_a.py::test_kept_first", "tests/unit/test_b.py::test_param"}
    )

    assert (result.text, result.removed, result.new) == (text, [], []), "nothing to remove or map"


PADDING_IDS = tuple(f"tests/unit/test_pad.py::test_pad_{n}" for n in range(4))
PADDING_ROWS = tuple(f"{test_id},scenario,cap,Req P,sc,high,name" for test_id in PADDING_IDS)
PADDING_COLLECTED = "".join(f"{test_id}\n" for test_id in PADDING_IDS)


@pytest.mark.parametrize(
    ("collected", "code"),
    [
        ("tests/unit/test_a.py::test_kept_first\n", EXIT_OK),
        (COLLECTED, EXIT_NEW_IDS),
    ],
    ids=["no-new-ids", "new-ids"],
)
def test_main_exits_one_only_when_ids_are_unmapped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], collected: str, code: int
) -> None:
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(_map_text(KEPT_FIRST, GONE, *PADDING_ROWS))
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(collected + PADDING_COLLECTED)

    status = main(["--map", str(csv_path), "--collect", str(collect_path)])

    out = capsys.readouterr().out
    assert status == code, "exit code follows the presence of unmapped ids"
    assert csv_path.read_text() == _map_text(KEPT_FIRST, *PADDING_ROWS), (
        "the map is rewritten without the gone row"
    )
    assert "test_gone" in out, "removed ids are printed"
    assert ("TestKlass::test_new" in out) is (code == EXIT_NEW_IDS), "new ids are printed"


def test_refresh_keeps_the_line_endings_of_the_map() -> None:
    crlf = _map_text(KEPT_FIRST, GONE).replace("\n", "\r\n")

    result = refresh(crlf, {"tests/unit/test_a.py::test_kept_first"})

    assert result.text == _map_text(KEPT_FIRST).replace("\n", "\r\n"), (
        "CRLF must survive the rewrite"
    )


COLLECT_ERROR_OUTPUT = "ERROR: file or directory not found: tests\n\nno tests ran in 0.01s\n"


def _run_main(tmp_path: Path, rows: tuple[str, ...], collected: str) -> tuple[int, Path, str]:
    csv_path = tmp_path / "map.csv"
    original = _map_text(*rows)
    csv_path.write_text(original)
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(collected)
    status = main(["--map", str(csv_path), "--collect", str(collect_path)])
    return status, csv_path, original


def test_a_collection_with_an_error_and_no_node_ids_leaves_the_map_untouched(
    tmp_path: Path,
) -> None:
    status, csv_path, original = _run_main(
        tmp_path, (KEPT_FIRST, GONE, KEPT_LAST), COLLECT_ERROR_OUTPUT
    )

    assert status == EXIT_COLLECTION_FAILED, "a failed collection must exit non-zero"
    assert csv_path.read_text() == original, "a failed collection must not erase the map"


def test_more_than_a_fifth_of_the_rows_going_refuses_the_rewrite(tmp_path: Path) -> None:
    status, csv_path, original = _run_main(
        tmp_path, (KEPT_FIRST, GONE, KEPT_LAST), "tests/unit/test_a.py::test_kept_first\n"
    )

    assert status == EXIT_REFUSED, "removing 2 of 3 rows must be refused, apart from a failed run"
    assert csv_path.read_text() == original, "a refused rewrite must leave the map as it was"


def test_the_two_ways_to_keep_the_map_have_their_own_exit_codes() -> None:
    codes = {EXIT_OK, EXIT_NEW_IDS, EXIT_COLLECTION_FAILED, EXIT_REFUSED, EXIT_MALFORMED_MAP}

    assert len(codes) == 5, "each outcome needs its own status for the caller to tell them apart"


@pytest.mark.parametrize(
    "map_text",
    [
        "",
        "level,capability\nscenario,cap\n",
        f"{HEADER}\ntests/unit/test_a.py::test_kept_first,scenario\n",
    ],
    ids=["empty", "no-test-column", "short-row"],
)
def test_a_malformed_map_exits_with_a_message_and_stays_as_it_was(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], map_text: str
) -> None:
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(map_text)
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(COLLECTED)

    status = main(["--map", str(csv_path), "--collect", str(collect_path)])

    assert status == EXIT_MALFORMED_MAP, "a malformed map must not end in a traceback"
    assert "malformed" in capsys.readouterr().out, "the message says what is wrong"
    assert csv_path.read_text() == map_text, "a malformed map is left as it was"


def test_a_failed_replace_leaves_the_map_whole_and_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = tmp_path / "map.csv"
    original = _map_text(KEPT_FIRST, GONE, *PADDING_ROWS)
    csv_path.write_text(original)
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text("tests/unit/test_a.py::test_kept_first\n" + PADDING_COLLECTED)

    def refuse(self: Path, target: Path) -> Path:
        raise OSError("disk gone")

    monkeypatch.setattr(Path, "replace", refuse)

    with pytest.raises(OSError, match="disk gone"):
        main(["--map", str(csv_path), "--collect", str(collect_path)])

    assert csv_path.read_text() == original, "the map is replaced whole or not at all"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["collect.txt", "map.csv"], (
        "the temporary file is removed when the replace fails"
    )
