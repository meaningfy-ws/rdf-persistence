<!-- Parents: GitHub issue #25; openspec/specs/rp-generation/spec.md
     ("Stale or edited generated output is detected"). Seeds: inputs/issue.md, inputs/seed.md. -->

# EPIC: The freshness fix hint names a command the application has

**Golden-thread parent:** GitHub issue #25 and the `rp-generation` requirement "Stale or edited
generated output is detected".

## Appetite

**TINY.** One concern: the text of one hint, and one optional setting that feeds it.

## Why

When generated code is stale, `rp-generate --check` and the pytest freshness plugin print
"run `make generate` to regenerate, then commit the result". An application whose target has
another name (MWB2 uses `make generate-models`) or no Makefile gets a command that does not exist,
and the adoption guide has to tell applications to name their target after the toolkit's message.

## Solution outline

By default the hint names the toolkit's own command, `rp-generate`, which every application has.
An application that regenerates another way says so in its `[tool.rp-generate]` entry with
`regenerate-command`, and both the CLI and the pytest plugin then name that command. The adoption
guide lets the target have any name.

## Key decisions

- **DEC-1**: The default hint names `rp-generate`. Source: issue #25 option 1. Rejected: keeping
  `make generate`.
- **DEC-2**: An optional `regenerate-command` key in `[tool.rp-generate]` overrides the command
  the hint names. Source: developer, 2026-11-08 (`inputs/seed.md` Q1). Rejected: default only.
- **DEC-3**: The key is a slot of the generated `GenerationTarget` model, added in
  `rp_generation.yaml` and regenerated (LinkML is the single source). Source: `AGENTS.md`, project
  specifics.

## Rabbit-holes

- Running the command for the developer. The hint names it; nothing executes it.
- Validating that the command exists. It is free text an application owns.

## No-gos

- No `rp-generate` command-line flag for the setting.
- No change to what the freshness check compares or to its exit codes.
- No renaming of this repository's own `make generate` target.

---

## What Changes

- `rdf_persistence/generation/model/rp_generation.yaml`: a `regenerate_command` slot on
  `GenerationTarget` (TOML key `regenerate-command`); regenerated code.
- `rdf_persistence/generation/config.py`: reads the key.
- `rdf_persistence/generation/manifest.py`, `cli.py`, `rdf_persistence/testkit/freshness.py`: the
  hint is built from the stale entries' commands instead of the constant `FIX_HINT`.
- `pyproject.toml`: this repository's entries set `regenerate-command = "make generate"`, so its own
  hint stays right.
- `docs/modules/ROOT/pages/howto/adopt.adoc` step 4: the target may have any name; the setting is shown.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-generation`: the freshness check's hint names the application's command.

## Impact

- The message of `rp-generate --check` and of the freshness plugin changes for applications that
  set nothing (`rp-generate` instead of `make generate`). No API or exit-code change.
- `[tool.rp-generate]` accepts one more optional key.
