"""Refresh `scenario-map.csv` against the collected tests (test-suite-grooming PD-16).

Standard library only. It reads `pytest --collect-only -qq` output (from a file, stdin or by
running pytest), reduces each node id to its function id (the `[case]` suffix dropped), removes
the map rows whose function is gone, and lists the function ids that have no row yet, for a
person to map. A row whose test file was renamed (`git diff --name-status -M --base`, or an
explicit `--moved OLD=NEW` file or folder pair) is re-keyed to the new path when the same function
is collected there; such rows do not count as removed. Without git the run goes on with no moves
and a warning line. Exit status: 0 when no id is unmapped, 1 otherwise; the map is kept untouched
with 2 when the collection failed (pytest status other than 0 or 5, or no node ids), 3 when more
than 20 % of the rows would be removed, and 4 when the map itself is malformed (no `test` column,
or a row shorter than the header). The rewrite goes through a temporary file, so the map is
replaced whole or not at all.
"""

import argparse
import csv
import io
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

EXIT_OK = 0
EXIT_NEW_IDS = 1
EXIT_COLLECTION_FAILED = 2
EXIT_REFUSED = 3
EXIT_MALFORMED_MAP = 4
PYTEST_OK = 0
PYTEST_NO_TESTS = 5
COLLECT_STATUSES = (PYTEST_OK, PYTEST_NO_TESTS)
MAX_REMOVED_SHARE = 0.2

CRLF = "\r\n"
LF = "\n"
NODE_SEPARATOR = "::"
CASE_OPEN = "["
TAB = "\t"
RENAME_STATUS = "R"
DEFAULT_BASE = "develop"
TEST_COLUMN = "test"
TEMP_SUFFIX = ".tmp"
STDIN_MARKER = "-"
DEFAULT_MAP = Path(__file__).with_name("scenario-map.csv")
COLLECT_COMMAND = ("uv", "run", "pytest", "tests", "--collect-only", "-qq", "-p", "no:randomly")


class MalformedMapError(ValueError):
    """The scenario map cannot be read as a table with a `test` column."""


class GitUnavailableError(RuntimeError):
    """The renames could not be read from git."""


@dataclass(frozen=True)
class Refresh:
    """The refreshed map text, the ids of removed and re-keyed rows and the ids with no row."""

    text: str
    removed: list[str]
    new: list[str]
    total: int
    rekeyed: list[tuple[str, str]] = field(default_factory=list)


def renames(name_status: str) -> dict[str, str]:
    """The `old -> new` file pairs of the `R<score>\\told\\tnew` lines of `git diff --name-status`."""
    moves: dict[str, str] = {}
    for line in name_status.splitlines():
        status, *paths = line.split(TAB)
        if status.startswith(RENAME_STATUS) and len(paths) == 2:
            moves[paths[0]] = paths[1]
    return moves


def git_renames(base: str) -> dict[str, str]:
    """The test files renamed since `base`; raises `GitUnavailableError` when git cannot say."""
    command = ["git", "diff", "--name-status", "-M", base, "--", "tests"]
    try:
        run = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise GitUnavailableError(str(error)) from error
    if run.returncode != 0:
        raise GitUnavailableError(run.stderr.strip() or f"git exited with {run.returncode}")
    return renames(run.stdout)


def _moved_pair(text: str) -> tuple[str, str]:
    """An `OLD=NEW` argument as a pair; anything else is a usage error."""
    old, separator, new = text.partition("=")
    if not (old and separator and new):
        raise argparse.ArgumentTypeError(f"expected OLD=NEW, got {text!r}")
    return old.rstrip("/"), new.rstrip("/")


def _moved_id(test_id: str, moves: dict[str, str]) -> str | None:
    """`test_id` at the path a move gives its file (a file or a folder prefix), if one does."""
    path, separator, rest = test_id.partition(NODE_SEPARATOR)
    for old, new in moves.items():
        if path == old or path.startswith(old + "/"):
            return new + path[len(old) :] + separator + rest
    return None


def function_ids(collect_output: str) -> set[str]:
    """The function ids of the collected node ids; non-node lines are ignored."""
    ids: set[str] = set()
    for line in collect_output.splitlines():
        node = line.strip()
        if NODE_SEPARATOR in node and " " not in node.split(CASE_OPEN, 1)[0]:
            ids.add(node.split(CASE_OPEN, 1)[0])
    return ids


def refresh(map_text: str, collected: set[str], moves: dict[str, str] | None = None) -> Refresh:
    """Re-key the rows of moved tests, drop those of functions not in `collected`, list new ids.

    A row whose id is gone is re-keyed when `moves` gives its file a new path at which the same
    function is collected (and no row holds that id already); otherwise it is dropped.
    """
    moves = moves or {}
    reader = csv.reader(io.StringIO(map_text))
    header = next(reader, None)
    if header is None or TEST_COLUMN not in header:
        raise MalformedMapError(f"no `{TEST_COLUMN}` column in the header")
    column = header.index(TEST_COLUMN)
    rows = [row for row in reader if row]
    for number, row in enumerate(rows, start=2):
        if len(row) < len(header):
            raise MalformedMapError(f"row {number} has {len(row)} of {len(header)} columns")
    held = {row[column] for row in rows}
    kept: list[list[str]] = []
    removed: list[str] = []
    rekeyed: list[tuple[str, str]] = []
    for row in rows:
        old = row[column]
        new = _moved_id(old, moves) if old not in collected else None
        if old in collected:
            kept.append(row)
        elif new in collected and new not in held:
            held.add(new)
            rekeyed.append((old, new))
            kept.append([*row[:column], new, *row[column + 1 :]])
        else:
            removed.append(old)
    mapped = {row[column] for row in kept}
    out = io.StringIO()
    writer = csv.writer(out, lineterminator=CRLF if CRLF in map_text else LF)
    writer.writerow(header)
    writer.writerows(kept)
    return Refresh(out.getvalue(), removed, sorted(collected - mapped), len(rows), rekeyed)


def _collect(source: str | None) -> tuple[str, int]:
    """The collect output and the pytest exit status (OK when read from a file or stdin)."""
    if source == STDIN_MARKER:
        return sys.stdin.read(), PYTEST_OK
    if source:
        return Path(source).read_text(), PYTEST_OK
    run = subprocess.run(COLLECT_COMMAND, capture_output=True, text=True, check=False)
    return run.stdout, run.returncode


def _write_whole(path: Path, text: str) -> None:
    """Write `text` to a temporary file beside `path`, then replace `path` with it."""
    temporary = path.with_name(path.name + TEMP_SUFFIX)
    try:
        with temporary.open("w", newline="") as handle:
            handle.write(text)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP, help="the scenario map CSV")
    parser.add_argument(
        "--collect",
        help=f"file with `pytest --collect-only -qq` output, or {STDIN_MARKER} for stdin "
        "(default: run pytest)",
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help=f"git ref the renamed test files are read against (default {DEFAULT_BASE})",
    )
    parser.add_argument(
        "--moved",
        type=_moved_pair,
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="a moved file or folder prefix, re-keying its rows; repeatable",
    )
    args = parser.parse_args(argv)
    with args.map.open(newline="") as handle:
        map_text = handle.read()
    collect_output, pytest_status = _collect(args.collect)
    collected = function_ids(collect_output)
    if pytest_status not in COLLECT_STATUSES or not collected:
        print(f"Collection failed (pytest status {pytest_status}, {len(collected)} ids): map kept")
        return EXIT_COLLECTION_FAILED
    moves: dict[str, str] = {}
    try:
        moves.update(git_renames(args.base))
    except GitUnavailableError as error:
        print(f"Warning: no moves from git against {args.base} ({error})")
    moves.update(args.moved)
    try:
        result = refresh(map_text, collected, moves)
    except MalformedMapError as error:
        print(f"The map {args.map} is malformed ({error}): map kept")
        return EXIT_MALFORMED_MAP
    if len(result.removed) > MAX_REMOVED_SHARE * result.total:
        print(f"Refused: {len(result.removed)} of {result.total} rows would go: map kept")
        return EXIT_REFUSED
    _write_whole(args.map, result.text)
    print(f"Re-keyed rows ({len(result.rekeyed)}):")
    print("\n".join(f"  {old} -> {new}" for old, new in result.rekeyed))
    print(f"Removed rows ({len(result.removed)}):")
    print("\n".join(f"  {test}" for test in result.removed))
    print(f"New ids with no row ({len(result.new)}):")
    print("\n".join(f"  {test}" for test in result.new))
    return EXIT_NEW_IDS if result.new else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
