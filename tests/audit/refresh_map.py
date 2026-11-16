"""Refresh `scenario-map.csv` against the collected tests (test-suite-grooming PD-16).

Standard library only. It reads `pytest --collect-only -qq` output (from a file, stdin or by
running pytest), reduces each node id to its function id (the `[case]` suffix dropped), removes
the map rows whose function is gone, and lists the function ids that have no row yet, for a
person to map. Exit status: 0 when no id is unmapped, 1 otherwise, 2 (map untouched) when the
collection failed (pytest status other than 0 or 5, or no node ids) or more than 20 % of the rows
would be removed.
"""

import argparse
import csv
import io
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

EXIT_OK = 0
EXIT_NEW_IDS = 1
EXIT_COLLECTION_FAILED = 2
PYTEST_OK = 0
PYTEST_NO_TESTS = 5
COLLECT_STATUSES = (PYTEST_OK, PYTEST_NO_TESTS)
MAX_REMOVED_SHARE = 0.2

CRLF = "\r\n"
LF = "\n"
NODE_SEPARATOR = "::"
CASE_OPEN = "["
TEST_COLUMN = "test"
STDIN_MARKER = "-"
DEFAULT_MAP = Path(__file__).with_name("scenario-map.csv")
COLLECT_COMMAND = ("uv", "run", "pytest", "tests", "--collect-only", "-qq", "-p", "no:randomly")


@dataclass(frozen=True)
class Refresh:
    """The refreshed map text, the ids of removed rows and the ids with no row."""

    text: str
    removed: list[str]
    new: list[str]
    total: int


def function_ids(collect_output: str) -> set[str]:
    """The function ids of the collected node ids; non-node lines are ignored."""
    ids: set[str] = set()
    for line in collect_output.splitlines():
        node = line.strip()
        if NODE_SEPARATOR in node and " " not in node.split(CASE_OPEN, 1)[0]:
            ids.add(node.split(CASE_OPEN, 1)[0])
    return ids


def refresh(map_text: str, collected: set[str]) -> Refresh:
    """Drop the rows of functions not in `collected`; list collected ids with no row."""
    reader = csv.reader(io.StringIO(map_text))
    header = next(reader)
    column = header.index(TEST_COLUMN)
    rows = [row for row in reader if row]
    kept = [row for row in rows if row[column] in collected]
    removed = [row[column] for row in rows if row[column] not in collected]
    mapped = {row[column] for row in rows}
    out = io.StringIO()
    writer = csv.writer(out, lineterminator=CRLF if CRLF in map_text else LF)
    writer.writerow(header)
    writer.writerows(kept)
    return Refresh(out.getvalue(), removed, sorted(collected - mapped), len(rows))


def _collect(source: str | None) -> tuple[str, int]:
    """The collect output and the pytest exit status (OK when read from a file or stdin)."""
    if source == STDIN_MARKER:
        return sys.stdin.read(), PYTEST_OK
    if source:
        return Path(source).read_text(), PYTEST_OK
    run = subprocess.run(COLLECT_COMMAND, capture_output=True, text=True, check=False)
    return run.stdout, run.returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP, help="the scenario map CSV")
    parser.add_argument(
        "--collect",
        help=f"file with `pytest --collect-only -qq` output, or {STDIN_MARKER} for stdin "
        "(default: run pytest)",
    )
    args = parser.parse_args(argv)
    with args.map.open(newline="") as handle:
        map_text = handle.read()
    collect_output, pytest_status = _collect(args.collect)
    collected = function_ids(collect_output)
    if pytest_status not in COLLECT_STATUSES or not collected:
        print(f"Collection failed (pytest status {pytest_status}, {len(collected)} ids): map kept")
        return EXIT_COLLECTION_FAILED
    result = refresh(map_text, collected)
    if len(result.removed) > MAX_REMOVED_SHARE * result.total:
        print(f"Refused: {len(result.removed)} of {result.total} rows would go: map kept")
        return EXIT_COLLECTION_FAILED
    with args.map.open("w", newline="") as handle:
        handle.write(result.text)
    print(f"Removed rows ({len(result.removed)}):")
    print("\n".join(f"  {test}" for test in result.removed))
    print(f"New ids with no row ({len(result.new)}):")
    print("\n".join(f"  {test}" for test in result.new))
    return EXIT_NEW_IDS if result.new else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
