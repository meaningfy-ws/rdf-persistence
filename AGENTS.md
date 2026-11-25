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
- **Rules:** this repository's rules for agents are in `docs/rules/`. At the start of an activity, the
  lead loads them with the rulebook skill; a subagent never loads them, its brief carries them
  (`rules.py load --activity <a> --brief`). Change them only through the rulebook, by pull request.
  Preferences and corrections go to the rulebook, never to the CLI's memory; project state goes to
  the spine and the repository's docs.
- **Where the rest lives, restated nowhere here:** the team, the stage loop and the lead's authority
  → `epic-delivery`; session hygiene, subagent dispatch and the tools table → `guardrails`; what to
  test and how each activity fails → `test-strategy`.

## Principles

1. **Layers.** `domain` is innermost. Direction: `entrypoints | adapters → services → domain`. The
   ports live in `services`, their implementations in `adapters`; `entrypoints` and `adapters`
   never import each other (the consumer's composition root wires them). `domain` imports no I/O,
   web, token or validation library. `testkit` sits outside the layers. The generator is a sibling
   top-level package, `rdf_persistence_generation/`, shipped in the same wheel; the library never
   imports it (`library-never-imports-the-generator`, no exception).
   `make check-architecture` enforces it.
2. **LinkML is the single source.** Every model artefact is generated from the LinkML schemas;
   never write or edit one by hand. Change the schema and run `make generate`; where a stock
   generator falls short, extend it in `rdf_persistence_generation/` with its own test. Data goes
   through the generated models, not bare dicts (PD-24 to PD-28).
3. **Generic only.** No consumer terms in the package, the tests or the architecture pages
   (`make check-docs`).
4. **Tests first**, in their tier (`unit`, `feature`, `integration`, `e2e`), stamped by folder.

## Working here

- Run everything through `make` (Python through uv); never bare `python` or `pytest`. The one
  exception is the narrow check below, `uv run pytest <file>`, which no make target covers. A gate
  prints its result, not its log; run a long command once in the background and wait for its notice. The
  hooks every session runs are `no-poll-loops` and `quiet-tools` from `meaningfy-core`; this
  repository ships none of its own.

  | Gate | When and who | Command |
  |---|---|---|
  | Narrow checks | the builder, each edit | the tests the edit touches (`uv run pytest <file>`), `make lint` |
  | Task gate | the builder, once per task | `make test-changed check-quality` |
  | Test seed | the lead, at stage start when builders will follow, in the background | `make test-seed` (selection data for `make test-changed`) |
  | Full gates | the lead, once per stage before the PR and once after the fix pass | `make check-all`; `make test-containers` when adapters changed |
  | Docs gate | the checker, when the docs change | `make check-docs` |
  | GitNexus | the lead, at stage start and before the stage's last commit; builders and reviewers run none | `make reindex`, then the GitNexus impact tool |

- **Guards for builders** (the machine is shared; the heavy lanes queue behind one lock,
  [`develop/testing.adoc#test-control`](docs/modules/ROOT/pages/develop/testing.adoc)): never run
  by hand `make test-fast` (it runs only as `make test-changed`'s fallback), `make test`,
  `make check-all`, `make test-seed` or `pytest --testmon`; wait for a long command through its
  completion notice, never `tail --pid`, `tail -f … | grep -m1` or a `timeout` around a wait; only
  the lead runs `make generate` or `uv sync` in a shared worktree.
- **Test control until skillery carries it** (meaningfy-ws/skillery#360; the mechanism here works
  without it, these steps stand in for what skillery does not yet say or enforce):
  - The lead's stage start is `make reindex`, then `make test-seed` as a background run, then the
    first briefs; builders do not wait for the seed. After `uv sync`, the lead seeds again. The
    seed only feeds builders' `make test-changed`: a session with no builders in that worktree
    (a rebase, the gates, a fix pass the lead does alone) skips it, since `make check-all` already
    runs every test.
  - Every builder brief pastes the guards above word for word (the brief checklist of
    [`develop/agents.adoc#brief`](docs/modules/ROOT/pages/develop/agents.adoc) carries them).
  - No hook enforces them yet: the lead reads each builder report for a full lane run by hand, a
    `tail --pid` / `tail -f | grep -m1` wait or a `uv sync`, and treats one as trigger T1
    (`epic-delivery`): re-brief, never accept the report as it stands.
  - Other repositories' sessions do not queue until they carry the queue: when a lane runs far
    slower than the durations table without having waited in the queue, the load comes from them,
    and fewer workers (the memory cap, or `PYTEST_N`) is the only lever here.
- Code tools: Serena for reading and editing symbols (a worktree is activated as its own Serena
  project), `ast-grep` for one code shape in many files, Grep for docs, YAML and the Makefile,
  GitNexus for blast radius. A HIGH or CRITICAL impact goes to the developer. Limits per role:
  [`develop/agents.adoc#tools`](docs/modules/ROOT/pages/develop/agents.adoc). GitNexus repo name:
  `rdf-persistence`. GitNexus guidance lives in this file only: `CLAUDE.md` never carries a
  GitNexus block (the `gitnexus:start` markers or a GitNexus heading that `gitnexus analyze`
  writes), which `make check-bindings` enforces.
- Edit in place (Edit or Serena), never with `sed -i` or a heredoc rewrite. Temporary files go in
  `temp/`.
- Branch off `develop` and open the PR into it; never commit to it. Commits follow
  `meaningfy-git-workflow`, the body wrapped at ~72 columns, the trace line naming the decisions
  (`Refs: <change-id> <task> PD-24`, or `Refs: #<issue>`). No AI attribution.
- A new docs page adds the question it answers to `questions.adoc`. A page the developer revised
  carries `:page-revised:` ([`develop/agents.adoc#revised`](docs/modules/ROOT/pages/develop/agents.adoc)).
