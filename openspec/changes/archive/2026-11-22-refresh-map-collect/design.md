<!-- PLAN (design half), retrospective: it records what was built in PR #294. EPIC:
     refresh-map-collect (proposal.md, #290). -->

# Design: refresh-map collects node ids whatever the ini verbosity

## Context

pytest gives `-v` and `-q` as relative steps on one verbosity level. `pytest.ini`'s addopts are
applied before the command line, so the ini's `-q` (−1) plus the refresher's `-qq` (−2) gave −3,
where `--collect-only` prints per-file counts. Node ids, one per line, are printed only at −1.
`function_ids` found none, and `main` exited `EXIT_COLLECTION_FAILED` (2).

## Decisions

- **PD-1 (DEC-1):** `COLLECT_COMMAND = ("uv", "run", "pytest", "tests", "--collect-only",
  "--verbosity=-1", "-p", "no:randomly")`. `--verbosity` stores the level outright, and the command
  line comes after the addopts, so the ini's `-q` no longer counts.
- **PD-2 (DEC-2):** the guard test takes the flags from `COLLECT_COMMAND`, runs
  `python -m pytest <its own module> <flags>` with `Popen`, and expects its own node id in the
  output.

## Test specification

| Id | Tier | Test | Proves |
|---|---|---|---|
| TC-1 | unit | `test_refresh_map.py::test_the_collect_command_prints_node_ids_whatever_the_ini_verbosity` | PD-1 under the real `pytest.ini` |

## Risks

None known. A pytest release that changes the meaning of `--verbosity` would fail TC-1.
