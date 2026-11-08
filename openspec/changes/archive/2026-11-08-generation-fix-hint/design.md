<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: EPIC `generation-fix-hint` (proposal.md), GitHub issue #25.

## Context

`FIX_HINT` (`rdf_persistence/generation/manifest.py:21`) is a constant. `cli.py:_freshness` appends
it as a `CheckProblem` when `freshness_problems` finds anything; `testkit/freshness.py` appends it to
the lines it passes to `pytest.exit`. `[tool.rp-generate]` is read by `config.py:_toml_entries` into
`GenerationTarget` models; it is a table or an array of tables (one row per schema), and TOML keys
equal field names except `schema` (→ `schema_file`, `TOML_SCHEMA_KEY`).

## Goals / Non-Goals

**Goals:** DEC-1 to DEC-3. **Non-Goals:** the EPIC's No-gos.

## Decisions

- **PD-1**: Slot `regenerate_command` (string, optional, no `ifabsent`) on `GenerationTarget`, with
  title, description and `slot_uri` like its neighbours, and **no `cli_flag` annotation**:
  `config.cli_flags()` turns every slot carrying one into an `rp-generate` flag, which the EPIC's
  No-gos exclude. The TOML key is `regenerate-command`: the
  key translation in `config.py` becomes a small mapping `{"schema": "schema_file",
  "regenerate-command": "regenerate_command"}` used by both `_toml_entries` and `_problems`, so an
  error names the TOML key. Rejected: a one-word key (`regenerate`): the developer chose the name in
  the issue.
- **PD-2**: Each entry carries its own command, because one `pyproject.toml` may hold several
  entries. The hint names the distinct commands of the **stale** entries, in entry order, joined by
  " or ": `run \`make generate-models\` to regenerate, then commit the result`. With two different
  commands: ``run `a` or `b` to regenerate, then commit the result``. Rejected: a project-level
  table (`[tool.rp-generate-settings]`): a second table for one string.
- **PD-3**: One function, `fix_hint(targets: Iterable[GenerationTarget]) -> str` in `manifest.py`,
  replaces `FIX_HINT`; it takes the stale targets and applies the default `rp-generate`
  (`DEFAULT_REGENERATE = "rp-generate"`). The CLI and the plugin both call it, so their texts
  cannot differ. To know which targets are stale, `manifest.py` gains
  `stale_targets(targets, base) -> list[tuple[GenerationTarget, list[CheckProblem]]]`, built on the
  existing `_target_problems`, listing only targets with at least one problem, so each target is
  compared once; `freshness_problems` becomes the
  flattening of it.
- **PD-4**: This repository sets `regenerate-command = "make generate"` on its four entries in
  `pyproject.toml`. The toy library (`tests/fixtures/library/pyproject.toml`) sets nothing, so its
  tests exercise the default.
- **PD-5**: The pytest plugin may check several projects (`rp_generate_projects`); it prints **one**
  hint at the end, naming the distinct commands of the stale targets of all projects.
- **PD-6**: **Behaviour change:** today the plugin adds the hint after a configuration error too
  (`testkit/freshness.py:35,48`). From now on a configuration error gets no hint, because no target
  is known and regenerating would fail on the same error. With stale targets and a configuration
  error together, the hint names only the stale targets' commands.

## Algorithm / approach

```python
def fix_hint(stale: Iterable[GenerationTarget]) -> str:
    commands = dict.fromkeys(t.regenerate_command or DEFAULT_REGENERATE for t in stale)
    return f"run {' or '.join(f'`{c}`' for c in commands)} to regenerate, then commit the result"
```

Worked example: MWB2's `pyproject.toml` has one entry with
`regenerate-command = "make generate-models"`; after a schema edit, `pytest` stops with

```
generated code is not fresh:
pyproject.toml: models/app.yaml changed since the last generation
run `make generate-models` to regenerate, then commit the result
```

A configuration error prints its error line and no hint (PD-6).

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Hand-edit `generated/rp_generation.py` | change `rp_generation.yaml`, `make generate` | LinkML single source |
| Keep `FIX_HINT` as a constant beside `fix_hint` | delete the constant; update its importers | two sources of the text |
| Assert on `make generate` in the toolkit's unit tests of the default | assert the default `rp-generate` and the override separately | the spec's two scenarios |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| `regenerate-command` is not a string | pydantic validation in `_toml_entries` | `ConfigError` naming `regenerate-command` |
| Unknown key misspelt (`regenerate_command` in TOML) | existing unknown-key refusal | `ConfigError` naming the key |
| Several stale entries with different commands | `fix_hint` dedupes in order | one hint naming each command once |

## Risks / Trade-offs

- [Applications that relied on the `make generate` wording] → a message, not an API; the change
  log says so.

## Open Questions

None.

## Review fixes (leader's decisions after the deep test and the five-lens review, 2026-11-08)

- **RF-1** (L1, L2, L5, deep test). A TOML row that uses a model field name which has its own TOML
  spelling (`regenerate_command`, `schema_file`) is refused like any unknown key, naming the key,
  as the error matrix already says. The one key table both translates and gates.
- **RF-2** (L1, deep test). `regenerate_command` gets a schema pattern: one line, not blank, no
  backtick (`^[^`\r\n]*[^`\s][^`\r\n]*$`). An empty, blank or backticked command is a
  `ConfigError` naming `regenerate-command`, not a silent fallback or a broken hint.
- **RF-3** (L2). The hint tests assert the exact strings of the spec and PD-2, not a copy of the
  formula; the mixed stale-and-error plugin test asserts exactly one hint.
- **RF-4** (L4). Names say what they hold: `_project_problems` → `_project_report`; the key maps
  `FIELD_OF_TOML_KEY` and `TOML_KEY_OF_FIELD`; `fix_hint`'s docstring states that `stale` is
  non-empty.
- Not taken: a shared `rp-generate` program-name constant (outside this change); reusing one
  flattening across `cli`, the plugin and `freshness_problems` (PD-3 keeps them); a `toml_key`
  annotation (one key does not justify it).
