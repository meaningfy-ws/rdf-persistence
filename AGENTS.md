<!-- meaningfy-template-version: 3.0.0 -->
<!-- CANONICAL, CLI-agnostic agent instruction file (opencode reads AGENTS.md natively; Claude Code
     reads it through the @AGENTS.md import in CLAUDE.md). Edit THIS file. It records only what is
     specific to this repository; the company standard, the skill routing and the spine conventions
     come from the global agent instructions and the installed skills (DEC-12). -->

# Project: RDF Persistence

The company-wide standard, the skill routing and the spine conventions (EPIC, PLAN, golden thread,
`/opsx:*`) live in your **global agent instructions** and the installed skills; this file does not
repeat them. Delivery follows skillery's **epic-delivery** skill; the page for people is
[`develop/agents.adoc`](docs/modules/ROOT/pages/develop/agents.adoc), and every test follows
[`develop/testing.adoc`](docs/modules/ROOT/pages/develop/testing.adoc). Rules for agents are in
`docs/rules/`: load them with the rulebook skill at the start of an activity; change them only
through it, by pull request.

## Code and layers

- Top-level package `rdf_persistence/` (no `/src`). The innermost layer is **`domain`** (the
  book's `models/`). Direction: `entrypoints | adapters → services → domain`. The ports live in
  `services`, their implementations in `adapters`; `entrypoints` and `adapters` never import each
  other (the consumer's composition root wires them). `domain` imports nothing upward and no I/O
  library; `generation` and `testkit` sit outside the layers. `make check-architecture` enforces it.
- **LinkML is the single source of specification (developer, 2026-11-05).** Every model artefact
  (domain and data classes, shapes, JSON-LD context and frames, TypeScript types, API and JSON
  schemas, diagrams) is generated from the LinkML schemas; never write or edit one by hand. Change
  the schema and run `make generate`. Where a stock generator falls short, extend it in
  `rdf_persistence/generation/` (subclass or template) with its own test. Data goes through the
  generated models, not bare dicts (design.md PD-24 to PD-28).
- **Where work is planned (developer, 2026-11-05, D-12).** In this repository's own spine,
  `openspec/changes/`, even when a consumer needs it. A consumer's change names the toolkit change
  id, and the toolkit change names the consumer need it serves.

## Tools

- Run everything through `make` (Python through uv); never bare `python`/`pytest`.
- **One tool per question.** Blast radius of a task: GitNexus `impact` (repo `rdf-persistence`).
  Outline of a file or a symbol's body: Serena's `serena_repl` tool with
  `s.lsp.get_symbols_overview` / `s.lsp.find_symbol` (with the body), not `Read` on a whole file.
  Who calls it: `s.lsp.find_referencing_symbols`. Replace or add a whole function:
  `s.edit.replace_symbol_body` / `s.edit.insert_after_symbol`. One code shape in many files:
  `ast-grep run -p '<pattern>' --lang python` (look at the matches, then add `-r '<rewrite>' -U`).
  Text in docs, YAML, AsciiDoc or the Makefile: Grep. The implementer and code-reviewer subagents
  have Serena, ast-grep and GitNexus too.
- **Edit in place** with the Edit tool or Serena; never rewrite files with Python heredocs or
  `sed -i`.
- Serena memories and `.claude/memory/` are not authority; the truth is `openspec/specs/`.
- Temporary files go in `temp/` (git-ignored), not `/tmp` or the session scratchpad.

## Branches, commits, PRs

- Default branch **`develop`**, the PR target and what consumers install. Branch off it; never
  commit to it. One PR per stage, merged only on green CI; a release comes last, so nothing is
  committed after the tag.
- **No AI attribution** in commits or PRs (`.claude/settings.json` enforces it for Claude Code).
- **Commit messages give the why and the what.** Subject: Conventional Commit, imperative, no
  trailing period. Body, wrapped at ~72 columns: **Why** first (the diff cannot show it), then
  **What** (one bullet per concern, naming the main files), then **Trace**
  (`Refs: <change-id> DEC-3`, and any `BREAKING CHANGE:` line). A one-line body only for trivial
  changes.

## Delivery: what this repo adds to epic-delivery

- **Subagents share this checkout and branch.** Builders run one after another and never stage or
  commit; the lead commits after each task. Writers run in parallel only on disjoint files;
  read-only agents may run in parallel freely. A worktree only for overlapping parallel work or
  when another session holds the checkout.
- **Every brief carries the standing rules:** models, not dicts; LinkML is the single source; the
  testing checklist; how to work (see `develop/agents.adoc`). The report names each make target run
  with its time and test count.
- **Gates.** Before handing out a task, the lead runs GitNexus `impact` once for it (stop and report
  HIGH/CRITICAL). The builder's task gate is one command, `make test-changed check-quality`
  (`make test-fast check-quality` after changing `domain` or a port in `services`). The lead reads
  the diff and the report and re-runs a gate only on an epic-delivery trigger (T1 to T3). After a
  red run, re-run only the failing tests until green, then the gate once. `make check-all` and
  `make test-containers` run once per stage, by the lead, before the PR; never in a task.
- **Challenge, kept cheap (developer, 2026-11-09).** The adversarial tester runs right after the
  riskiest task (new invariants, write order, concurrency); review lenses L4 and L5 are one pass;
  the checker reads the lead's `make check-all` result and does not re-run tests.
- **Re-index GitNexus once per stage**, at its start, before the first impact check:
  `gitnexus analyze --embeddings --skip-agents-md --skip-skills` (≈ 20 s). If it errors
  (developer, 2026-11-09), do not retry or investigate: run `gitnexus clean --force` and the same
  `analyze` again (≈ 4 min, in the background), then revert anything it wrote to `AGENTS.md`,
  `CLAUDE.md` or `.claude/skills/`.
- **Never poll.** Run long commands in the foreground (timeout up to 10 min), in the background
  with its notice, or wait with the Monitor tool; a hook denies `sleep` loops in Bash.

## Docs

- `make check-docs`: no consumer terms in `docs/modules/ROOT/pages/architecture/`; every page in
  the nav.
- Docs open with questions: add the question a new page answers to `questions.adoc`. Keep the
  durations table in `develop/index.adoc` from ordinary runs (no profiling).
- **Pages the developer revised (developer, 2026-11-10).** When the developer says they revised a
  page, add `:page-revised: <date> by the developer` under its `:description:` line, or move the
  date forward. Only the developer's word sets or moves it. List them with
  `grep -rl ':page-revised:' docs/`.
