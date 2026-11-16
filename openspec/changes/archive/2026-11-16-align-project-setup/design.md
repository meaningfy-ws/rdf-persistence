<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: EPIC `align-project-setup` (proposal.md).

## Context

`.coveragerc` omitted `rdf_persistence/adapters/*` from the floor, although their unit tests reach
97–100 % of every adapter but `redis_events.py` (0 %: it needs Redis). Release-please ran the
`python` strategy, which writes the version into `pyproject.toml`.

## Goals / Non-Goals

**Goals:** DEC-1 to DEC-4. **Non-Goals:** the EPIC's No-gos.

## Decisions

- **PD-1**: `.coveragerc` omits only `adapters/redis_events.py` and `testkit/containers/*`.
- **PD-2**: Release-please runs the `simple` strategy with `version-file: VERSION`; `pyproject.toml`
  (`$.project.version`) and `uv.lock` are its extra files. `make check-version` greps
  `version = "<VERSION>"` in `pyproject.toml` and runs inside `check-spec-docs`.
- **PD-3**: `ruff.toml` takes the template's selection and per-file ignores (`PLR2004` in tests);
  `PLR0913` is ignored in tests (pytest fixtures arrive as arguments) and listed per production
  file under a debt comment. Each `# noqa` names its reason.
- **PD-4**: `AGENTS.md` keeps what the project is, how it is developed (routed to skillery) and its
  principles; tools per role, gates, re-indexing and revised pages move to `develop/agents.adoc`.
