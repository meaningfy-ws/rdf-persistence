<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

Copied verbatim from GitHub on 2026-11-08.

# Issue #25: generation: freshness fix hint hard-codes the consumer's 'make generate' target

https://github.com/meaningfy-ws/rdf-persistence/issues/25

## Summary
The freshness check's fix hint is hard-coded to the consumer's make target name: `FIX_HINT = "run \`make generate\` to regenerate, then commit the result"` (`rdf_persistence/generation/manifest.py:21`). An application whose regeneration target has another name (or no Makefile) gets a hint naming a command that does not exist, and the adoption guide has to tell applications to name their target `make generate` to match.

## Context
- Consumer: MWB2 (mapping-workbench-v2). Its architecture decision on model-driven code names the regeneration target `make generate-models`; the toolkit's hint would tell its developers to run `make generate`.
- The consumer will harmonise its gate names with the toolkit's later; the toolkit should still not dictate a consumer's build-tool vocabulary through an error message.
- rdf-persistence commit: `e5ca99d116338f0d06530fe127493f1c3c5d3a67` (develop).

## Current behaviour
- `rp-generate --check` (via `cli.py:51`) and the pytest freshness plugin (`testkit/freshness.py:48`) both print `FIX_HINT` verbatim.
- `howto/adopt.adoc` step 4: "Add a `make generate` target, since the checks' error messages name it".

## Expected behaviour / proposed capability
The hint names a command the application actually has. Two options, smallest first:
1. Default the hint to the toolkit's own command, which always exists: `run \`rp-generate\` to regenerate, then commit the result`.
2. Additionally let the application say how it regenerates, in the existing `[tool.rp-generate]` table:
```toml
[tool.rp-generate]
schema = "models/app.yaml"
package = "app.domain.generated"
regenerate-command = "make generate-models"   # used in the freshness hint; default "rp-generate"
```
Then both the CLI and the freshness plugin print `generated code is not fresh: ... run \`make generate-models\` to regenerate, then commit the result`. The adoption guide then says the target may have any name.

## Why it belongs in rdf-persistence
The message is produced by the toolkit for every application; only the toolkit can make it correct. Any workaround in an application (renaming its targets to suit the message, wrapping the plugin to rewrite it) bends the application to a toolkit detail.

## Acceptance
- **Given** an application with no `regenerate-command`, **when** the freshness check fails, **then** the hint names `rp-generate`.
- **Given** `regenerate-command = "make generate-models"`, **when** the freshness check fails through the CLI or the pytest plugin, **then** the hint names `make generate-models`.
- **Given** the adoption guide, **when** it describes the make targets, **then** it no longer requires the name `make generate`.

## Impact on the consumer
Not blocking; the consumer's project setup will create its targets after this is decided.

