# Hand-over: otel-observability, after stage 1

## Done
Stage 1 (one log context, one logging style, tasks 1.1–1.5), PR #149 (merged by the
watch-and-merge command after this note). The developer granted the lead commit, push, PR and
merge after a local `make check-all` on the rebased branch (D-2).

## Decided since the PLAN
D-1 to D-7 (design.md, Delivery decisions), and the stage 1 floor list. D-4 extends our pydantic
generator (a dotted alias names no field; `ds_name` became `fuseki_dataset_name`); D-5 enables the
`pydantic.mypy` plugin.

## Open
- **Carried to task 2.1 (D-6):** the guard of PD-9 must require `extra=log_extra(...)` on every
  log call (W1), and the `error_type` slot's description must allow a service code (S3); fix
  PD-9's wording and regenerate.
- **`technical-models` stage 3 in flight** (D-1): its tasks 3.2 and 3.3 change the constructors of
  `FusekiStore`, `RedisEventBus`, `Relay`, `MessageBus`; stage 2's tasks 2.2 to 2.4 touch the same
  classes. Rebase on `origin/develop` before the PR; place PD-13's `middlewares=` after its settings
  group parameter; follow its paths if they move.
- `make test-containers` exits 2 on a failed test even when a wrapper hides it: read the exit code,
  not the tail.
- Builders in a worktree run `make`, `uv` and file writes with the sandbox disabled; narrow checks
  use `uv run --all-extras pytest …`. Builders tick no `tasks.md` box (the lead does, once).
- Review set (D-3): stage 2 runs the full review once (L1, L2, L3 as separate passes, L4+L5 as
  one) and a checker; no adversarial tester (MEDIUM, no `## Invariants`).

## Next
Stage 2, task 2.1, on `change/otel-observability-s2` off the latest `develop`. Read first:
tasks.md §Stage 2, design.md PD-3 to PD-5, PD-10, PD-11, PD-13, D-6, DEC-4 to DEC-7, DEC-10,
DEC-11; `specs/rp-observability`. Tasks 2.3 and 2.4 touch disjoint files and can run in parallel
after 2.1; 2.2 touches the store port and the kit (run it before them, `make test-fast`).

## Prompt
Act as the team lead (epic-delivery); read docs/modules/ROOT/pages/develop/agents.adoc. Deliver
stage 2 of openspec/changes/otel-observability from handover.md: one PR into develop from branch
change/otel-observability-s2 off the latest develop. Rebase before the PR; merge only after local
make check-all passes on the rebased branch. Run independent tasks as parallel subagents.
