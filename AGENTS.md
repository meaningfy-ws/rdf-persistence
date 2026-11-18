<!-- meaningfy-template-version: 3.0.0 -->
<!-- CANONICAL, CLI-agnostic agent instruction file (opencode reads AGENTS.md natively; Claude Code
     reads it through the @AGENTS.md import in CLAUDE.md). Edit THIS file. Keep it to what the
     project is, how it is developed and its principles; explanations go in docs/. -->

# RDF Persistence

## What this project is

`rdf-persistence` is a toolkit for model-driven RDF applications: a library, a code generator and
a service kit. A LinkML model generates the domain classes, shapes, JSON-LD context and frames,
TypeScript types and the API; the library stores the resulting aggregates in triple stores, with
transactions, tenancy, events and access control. Its first consumer is MWBv2 (Mapping Workbench
v2), a separate repository that depends on this one, never the reverse: anything generic to
model-driven RDF applications lives here, anything consumer-specific lives there.

Archetype: library. Python 3.12, uv, top-level package `rdf_persistence/`, default branch
`develop`, version in `VERSION`. Orientation: `openspec/config.yaml` `context:`. Truth: the `rp-*`
capabilities in `openspec/specs/`. Docs: `docs/` (Antora); start with `questions.adoc`.

## How it is developed

By the Meaningfy method in skillery (`meaningfy-core`, `meaningfy-building`), routed by your
global instructions; this file adds only what is specific to this repository. If your global
instructions are missing, route by the skills' descriptions and say so once.

- **The spine is `openspec/`.** EPIC ≡ `openspec/changes/<id>/proposal.md`; PLAN ≡ `design.md` +
  `tasks.md`, clarity-gated ≥ 9/10, `tasks.md` citing its EPIC id on its first line. Drive it with
  `/opsx:*` (Claude Code) or `opsx-*` (opencode). superpowers artifacts land in the spine, never in
  `docs/superpowers/`.
- **Work a consumer needs is planned here** (D-12): the consumer's change names the toolkit change
  id, and the toolkit change names the need it serves.
- **Delivery** follows `epic-delivery`; tests follow
  [`develop/testing.adoc`](docs/modules/ROOT/pages/develop/testing.adoc). What this repository adds
  (briefs, gates, review set, tools per role, re-indexing) is in
  [`develop/agents.adoc`](docs/modules/ROOT/pages/develop/agents.adoc): the lead reads it at the
  start of an epic session.
- **Rules:** this repository's rules for agents are in `docs/rules/`. At the start of an activity, load them with the rulebook skill; change them only through it, by pull request. Preferences and corrections go to the rulebook, never to the CLI's memory; project state goes to the spine and the repository's docs.

## Principles

1. **Layers.** `domain` is innermost. Direction: `entrypoints | adapters → services → domain`. The
   ports live in `services`, their implementations in `adapters`; `entrypoints` and `adapters`
   never import each other (the consumer's composition root wires them). `domain` imports no I/O,
   web, token or validation library. `generation` and `testkit` sit outside the layers.
   `make check-architecture` enforces it.
2. **LinkML is the single source.** Every model artefact is generated from the LinkML schemas;
   never write or edit one by hand. Change the schema and run `make generate`; where a stock
   generator falls short, extend it in `rdf_persistence_generation/` with its own test. Data goes
   through the generated models, not bare dicts (PD-24 to PD-28).
3. **Generic only.** No consumer terms in the package, the tests or the architecture pages
   (`make check-docs`).
4. **Tests first**, in their tier (`unit`, `feature`, `integration`, `e2e`), stamped by folder.

## Working here

- Run everything through `make` (Python through uv); never bare `python` or `pytest`. Task gate:
  `make test-changed check-quality` (`make test-fast check-quality` after changing `domain` or a
  port). The full gates, `make check-all` and `make test-containers`, are the lead's.
- Code tools: Serena for reading and editing symbols, `ast-grep` for one code shape in many files,
  Grep for docs, YAML and the Makefile, GitNexus impact by the lead. Limits per role:
  [`develop/agents.adoc#tools`](docs/modules/ROOT/pages/develop/agents.adoc).
- Edit in place (Edit or Serena), never with `sed -i` or a heredoc rewrite. Temporary files go in
  `temp/`.
- Branch off `develop` and open the PR into it; never commit to it. Commits follow
  `meaningfy-git-workflow`, the body wrapped at ~72 columns, the trace line naming the decisions
  (`Refs: <change-id> <task> PD-24`, or `Refs: #<issue>`). No AI attribution.
- A new docs page adds the question it answers to `questions.adoc`. A page the developer revised
  carries `:page-revised:` ([`develop/agents.adoc#revised`](docs/modules/ROOT/pages/develop/agents.adoc)).
