<!-- meaningfy-template-version: 3.0.0 -->
<!-- CANONICAL, CLI-agnostic agent instruction file (opencode reads AGENTS.md natively; Claude Code
     reads it through the @AGENTS.md import in CLAUDE.md). Edit THIS file. CLAUDE.md is a thin
     pointer that adds only Claude-specific guidance — never a symlink, never a copy. This file
     ROUTES to skills and to the global standard; it never restates that standard (DEC-12 —
     global vs repo split). -->

# Project: RDF Persistence

Meaningfy project. Build clean, layered, well-tested code; minimise WTFs-per-minute. The
company-wide standard (Clean Code, Clean Architecture, testing, tooling) lives in your **global
agent instructions** (`~/.claude/CLAUDE.md` on Claude Code, `~/.config/opencode/AGENTS.md` on
opencode) — this file does **not** repeat it; it ROUTES to it and to the
installed skills, and records only what is specific to **this** repo.

## Skill routing (use the skill for the task)

- Structuring Python code (domain/adapters/services/entrypoints, SOLID, CI) → **cosmic-python**
- Keeping code minimal — YAGNI, avoid over-engineering, simplest working approach → **ponytail**
  (`/ponytail` to set intensity; `/ponytail-review` for a delete-list on the diff)
- System / solution design (C4, ADRs, contracts) → **architecture**
- Modelling the domain / generating code from a model (`make generate-models`) → **conceptual-modelling**
  (product repos only)
- Any new feature or non-trivial change → start by exploring options (**superpowers:brainstorming**)
- Any feature or bugfix implementation → **superpowers:test-driven-development** (tests first)
- Debugging → **superpowers:systematic-debugging**
- Shaping an EPIC + deriving its PLAN → **epic-planning** + the opsx workflow commands
  (`/opsx:*` on Claude Code, `opsx-*` on opencode)
- Spec readiness (the PLAN clarity gate, ≥9/10) → **clarity-gate**
- BDD features → **bdd-gherkin**
- Commits / branches / PRs → **meaningfy-git-workflow** (mechanics via **commit-commands**)
- Pre-PR review → **meaningfy-code-review** (+ external **code-review**)
- Deploy / release / versioned image (deployable repos) → **ci-cd-delivery**
- Docs → **technical-writing**

If a request conflicts with these, flag it before proceeding.

## The spine — where work is shaped and remembered

This repo carries the Meaningfy **spine** under `openspec/` (OpenSpec, schema `meaningfy`):

- **EPIC ≡ `openspec/changes/<id>/proposal.md`** (the Shape-Up work shape: appetite, why, solution,
  key decisions, rabbit-holes, no-gos).
- **PLAN ≡ `openspec/changes/<id>/design.md` + `tasks.md`** (the clarity gate scores the pair ≥9/10).
- **Normative requirements ≡ `openspec/changes/<id>/specs/<cap>/spec.md`** (RFC-2119 SHALL +
  Given/When/Then; no EARS). They merge into **`openspec/specs/`** — the durable truth — on archive.
- **Seed inputs** (briefs, notes) live in `openspec/changes/<id>/inputs/` — preserved, never groomed.
- **Orientation** is `openspec/config.yaml`'s `context:` field (the native index) — **not** a
  hand-curated MEMORY.md. The truth is `openspec/specs/`.

Drive it with the opsx workflow commands (`/opsx:*` on Claude Code, `opsx-*` on opencode): `propose`,
`explore`, `apply`, `sync`, `archive` — core profile.

**External method skills land in the spine (binding).** `superpowers` provides *disciplines*, not a
parallel spec system — its artifacts MUST land in `openspec/changes/<id>/`, never a `docs/superpowers/`
tree. A **brainstorming** design feeds the **EPIC** (`proposal.md`); **writing-plans is SUPERSEDED** by
the **PLAN** (`design.md`+`tasks.md`); execution uses superpowers TDD, tracked via the opsx `apply`
command.

**Golden thread (cite your parent).** Each artifact cites the one above it: the PLAN (`tasks.md`)
cites its EPIC id on the first line; specs cite their capability; commits reference the change. This
is how any commit traces up to the requirement that justifies it.

## Implementation loop (orchestration)

Before editing a symbol, run gitnexus impact (status → analyze → impact/context); stop and
report HIGH/CRITICAL risk. Loop: generate (tests first) → verify (run tests) → integrate
(present, get consent). On a design-level failure, fix the spec, not the code (Rule of
Divergence). Commit only on explicit developer consent.

## Working conventions

- The innermost layer is **`domain`** (the book's `models/`). Direction:
  `entrypoints → services → domain`, `adapters → domain`. `domain` imports nothing upward.
  Enforced by `.importlinter`; checked via `make check-architecture`.
- Run Python tooling through uv (`uv run pytest`, `uv run ruff`, …). Never invoke
  bare `python`/`pytest` — prefer the `make` targets below.
- **Subagents** — before spawning one, follow *Subagent dispatch* in the `guardrails` skill: spawn
  only when it pays, brief it fresh, take the base report back, and have finished work checked by a
  second subagent.
- **Subagents share this checkout and branch.** Implementers run one after another; the leader
  commits after each task. Run writers in parallel only on tasks with disjoint files, and they
  never stage or commit. Read-only agents (reviewers, Explore) may run in parallel freely. Use a
  separate worktree (`isolation: "worktree"`) only for overlapping parallel work or when another
  session holds this checkout.
- **Run checks through make** (`make test`, `make check-all`); don't hand-roll pytest pipelines.
- **Temporary files** go in `temp/` (git-ignored), not `/tmp` or the session scratchpad.
- **Commits and PRs carry no AI attribution** (no `Co-Authored-By`, no "Generated with" line).
  Enforced for Claude Code by `.claude/settings.json` (`attribution` empty); other agents follow
  this rule by hand.
- **Commit messages are descriptive and give the why and the what.** Subject: Conventional
  Commit, imperative, no trailing period (`feat(store): add named-graph upsert`). Body,
  after one blank line, wrapped at ~72 columns:
  1. **Why** — the problem, motivation or constraint; the diff cannot show it, so it comes first.
  2. **What** — the changes in plain words, one bullet per concern, naming the main files or
     modules, so a reviewer knows what to look for without reading the diff first.
  3. **Trace** — the change id and decisions it implements (`Refs: <change-id> DEC-3`),
     and any BREAKING change on its own `BREAKING CHANGE:` line.
  A one-line body is fine only for trivial changes (typo, formatting). No AI attribution.

## Team leader — the main agent orchestrates (developer, 2026-11-03)

The main agent is the **team leader**: it owns the conversation with the developer, the plan, the
decisions and the integration; team members (subagents) do the bounded work. Dispatch rules are in
*Subagent dispatch* (`guardrails` skill) — this section only names the roles and what the leader
keeps.

- **The team** (catalogue agents first):
  - planning an EPIC/PLAN → `meaningfy-building:epic-planner` (returns question rounds; the leader
    asks the developer and relays answers);
  - one ready task in `tasks.md` → `meaningfy-building:implementer` (test-first, one task per brief);
  - pre-PR review → `meaningfy-building:code-reviewer`, one per lens (L1–L5), in parallel;
  - wide code search → `Explore`; anything else → `general-purpose`.
- **The leader keeps:** talking to the developer, every decision, gitnexus impact before a task
  is handed out, running `make` checks after each member returns, commits (on consent), and
  updates to the spine. Members never ask the developer directly and never commit.
- **Precise briefs.** Each brief names the change id and task number, the files in scope as paths,
  decisions already made (cite `DEC-n` / the spec scenario), what is out of scope, and the report
  expected. If the leader cannot write that brief, the task is not ready — fix the PLAN first.
- **Trust, then verify.** A member's report is a claim: the leader re-runs the checks and reads the
  diff before marking a task done, and has finished work checked by a second member.
- **Do it inline** when it is a few tool calls or the next step depends on it — delegation is for
  bounded, independent work, not for every step.
- Default branch is **`develop`** (the PR target). Branch off it; never commit to it
  directly.

## `.claude/` is a regenerable index — the truth is `openspec/specs/`

`.claude/memory/MEMORY.md` is a cheap orientation note (≤200 lines; stable patterns only). It is an
**index, not authority** — if it disagrees with `openspec/specs/`, `specs/` wins. The legacy
`.claude/memory/epics/EPIC.md`+`PLAN.md`+`task.md` model is **superseded** by the spine's native
artifacts above; do not reintroduce parallel epic files under `.claude/`.

## Project specifics

- **Where work is planned (developer, 2026-11-05).** rdf-persistence is co-developed with its first
  consumer and planned from that consumer's spine: new EPICs live in the consumer repository's
  `openspec/changes/`, with this toolkit's capabilities named `rp-<capability>`. This repository's
  `openspec/changes/` keeps its earlier changes (`soa-python-rdf-orm`, archived 2026-11-05 under `archive/`); new changes here are opened
  only for work that no consumer EPIC carries. Commits here cite the planning change id
  (`Refs: <change-id> ...`); PRs target `develop`, which the consumer installs.
- **Docs check:** `make check-docs` (no consumer terms in `docs/modules/ROOT/pages/architecture/`;
  every page in the nav).

<!-- Fill these in for this repository. Delete the guidance comments once resolved. -->

- **Archetype:** <!-- product | library | doc-only -->
- **Top-level package(s):** `rdf_persistence/` (no `/src`). Multiple deployable units → multiple
  top-level packages.
- **Modules / bounded contexts:** <!-- e.g. billing, notifications, commons -->
- **Domain model:** <!-- product only — model/ (LinkML); `make generate-models` regenerates targets -->
- **Datastores / external systems:** <!-- e.g. MongoDB, Redis, the ERE engine, an OpenAPI client -->
- **Deployable?** <!-- yes/no — if yes, see ci-cd-delivery; CD stub pending DevOps ratification -->
- **Make targets:** <!-- the dev UX — e.g. make install, make check-all, make test, make build-docs -->
- **GitNexus repo name:** <!-- the name this repo is indexed under (gitnexus_*) -->

See `docs/` for methodology (ai-coding), standards (engineering-standards), and philosophy.
