# Design: ci-minimal-gate

> Derives from: the EPIC `ci-minimal-gate` (proposal.md, DEC-1 to DEC-5).

## PD-1 Split one workflow into two

`ci.yaml` keeps the jobs `style`, `types`, `architecture`, `spec-docs-generation` and `feature`,
each calling one make group as today. Its `on:` keeps only `pull_request` into `develop`, with the
same `paths-ignore`. `concurrency` and `permissions` stay.

`nightly.yaml` takes the jobs `unit-shard`, `unit`, `sonar` and `test-generator` verbatim from
`ci.yaml`, with the same `needs:` and artifact names (D-15, D-19 of `generator-package` still hold).
Its `on:` is `schedule: cron "0 2 * * *"` (02:00 UTC) and `workflow_dispatch`. A scheduled run
checks out the default branch, `develop`. Its concurrency group is `nightly`, without cancelling a
run in progress.

## PD-2 The tests follow the jobs

`tests/unit/tooling/test_lanes.py` reads the shard, coverage-combine, generator and Sonar jobs from
`nightly.yaml` instead of `ci.yaml`. New tests pin the split: `ci.yaml` runs on pull requests only
and has exactly the five gate jobs, with no `test-unit-ci` and no `test-generator`; `nightly.yaml`
runs on a schedule and by hand.

## PD-3 Docs and comments

`develop/testing.adoc#slow` says what the PR gate runs and that the full suite runs nightly and in
`make check-all`; `develop/index.adoc` names the nightly job where it names the CI generator job;
the Makefile's comments name the workflow each group runs in; `sonar-project.properties` names
`nightly.yaml`; the README badge reads `nightly.yaml`.

## Verification

`uv run pytest tests/unit/tooling/test_lanes.py`, `make lint`, `make check-spec`, `make check-docs`.
The lead runs `make check-quality` for the task gate; no library code changes, so `make check-all`
adds nothing a lane test would not show. After merge, the developer triggers `nightly.yaml` once
by hand (`gh workflow run nightly.yaml --ref develop`) and checks it is green.
