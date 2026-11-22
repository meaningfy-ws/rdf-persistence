<!-- Parents: issue #290; archive/2026-11-16-test-suite-grooming PD-16 (the scenario map and its
     refresher). Found on the way by slot-resolution (#276, PR #288), tenant-root-owned-parts and
     abstract-collection-member-class.
     Retrospective: written on 2026-11-22 after the fix merged (PR #294, 55ec398, commit cf6757e),
     at the developer's request. The fix ran as a side task of the slot-resolution session, without
     a change or a PLAN gate. -->

# EPIC: make refresh-map collects node ids whatever the ini verbosity

## Appetite

**TINY.** One constant in `tests/audit/refresh_map.py` and one test. Test tooling only.

## Why

`make refresh-map` (test-suite-grooming PD-16) stopped every run with `Collection failed (pytest
status 0, 0 ids): map kept`. Since 6ae9c643, `pytest.ini`'s addopts carry `-q`. The refresher
collected with a relative `-qq`, so pytest ran at `-qqq` and printed per-file counts
(`tests/e2e/test_library.py: 11`) instead of node ids. Three sessions on 2026-11-22 had to work
around it with `--collect` on a hand-made collection.

## Solution outline

Collect with `--verbosity=-1`, which sets the level outright instead of adding to the ini's, and
add a test that runs the command's own flags and expects a node id back. A later change to
`pytest.ini` then fails that test instead of breaking the target silently.

## Key decisions

- **DEC-1:** use `--verbosity=-1`. Rejected: dropping `-qq` (it would rely on the ini's `-q`
  staying exactly as it is) and `-o addopts=""` with `-q` (it would drop the ini's other options
  from the collection too).
- **DEC-2:** the guard test runs the real flags against its own module through `Popen`, not
  `run`, because the module's autouse fixture fakes `subprocess.run` for the git calls.

## Rabbit-holes

None.

## No-gos

- No change to `pytest.ini`.
- No change to the map's format or the refresher's exit codes.

---

## What Changes

- `tests/audit/refresh_map.py`: `COLLECT_COMMAND` uses `--verbosity=-1`, and the module docstring
  says so.
- `tests/unit/tooling/test_refresh_map.py`: the new test
  `test_the_collect_command_prints_node_ids_whatever_the_ini_verbosity`.
- `tests/audit/scenario-map.csv`: a row for the new test.

## Capabilities

None. The refresher is test tooling. No `rp-*` capability states its behaviour:
test-suite-grooming kept it in its design (PD-16), not in a spec. The change is archived with
`--skip-specs`.

## Impact

Developers and leads only: `make refresh-map` works again. No library, generator or consumer
impact.

## As built

Delivered in one PR, #294 (merge `55ec398`), as shaped. Its commit referenced #289 rather than
#290, so the issue was closed by hand on 2026-11-22 with a comment naming the merge. Checked on
develop: `make refresh-map` exits 0 with no unmapped ids, and `test_refresh_map.py` passes.
