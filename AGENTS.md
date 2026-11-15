<!-- meaningfy-template-version: 3.0.0 -->
<!-- CANONICAL, CLI-agnostic agent instruction file (opencode reads AGENTS.md natively; Claude Code
     reads it through the @AGENTS.md import in CLAUDE.md). Edit THIS file. It holds the rules agents
     follow here; develop/agents.adoc explains them for people. The shared Meaningfy part (habits,
     tool list per activity) will come from skillery's project-setup template. -->

# Project: RDF Persistence

## Where the shared standard lives

The company standard and the skill routing are in your global agent instructions
(`~/.claude/CLAUDE.md` on Claude Code, `~/.config/opencode/AGENTS.md` on opencode) and the
installed Meaningfy skills. If your global file is missing, route by the skills' descriptions and
say so once. Two rules from it bind here whatever your setup:

- **The spine is `openspec/`.** Orientation is `openspec/config.yaml` `context:`; the truth is
  `openspec/specs/`. EPIC ≡ `openspec/changes/<id>/proposal.md`; PLAN ≡ `design.md` + `tasks.md`
  (clarity-gated ≥ 9/10); `tasks.md` cites its EPIC id on its first line. Drive it with `/opsx:*`
  (Claude Code) or `opsx-*` (opencode).
- **superpowers artifacts land in the spine**, never in `docs/superpowers/`: brainstorming feeds
  `proposal.md`, and writing-plans is superseded by `design.md` + `tasks.md`.

Delivery follows the **epic-delivery** skill, tests follow
[`develop/testing.adoc`](docs/modules/ROOT/pages/develop/testing.adoc), and the reasons behind the
rules below are in [`develop/agents.adoc`](docs/modules/ROOT/pages/develop/agents.adoc). Rules for
agents are in `docs/rules/`: load them with the rulebook skill at the start of an activity; change
them only through it, by pull request.

## Code and layers

- Top-level package `rdf_persistence/` (no `/src`). The innermost layer is **`domain`** (the
  book's `models/`). Direction: `entrypoints | adapters → services → domain`. The ports live in
  `services`, their implementations in `adapters`; `entrypoints` and `adapters` never import each
  other (the consumer's composition root wires them). `domain` imports nothing upward and no I/O,
  web, token or validation library; `generation` and `testkit` sit outside the layers.
  `make check-architecture` (`.importlinter`) enforces it.
- **LinkML is the single source of specification (developer, 2026-11-05).** Every model artefact
  (domain and data classes, shapes, JSON-LD context and frames, TypeScript types, API and JSON
  schemas, diagrams) is generated from the LinkML schemas; never write or edit one by hand. Change
  the schema and run `make generate`. Where a stock generator falls short, extend it in
  `rdf_persistence/generation/` (subclass or template) with its own test. Data goes through the
  generated models, not bare dicts. The freshness check, the conformance suite and the model
  guards enforce this (PD-24 to PD-28 in
  `openspec/changes/archive/2026-11-06-toolkit-v1-foundation/design.md`).
- **Where work is planned (developer, 2026-11-05, D-12 in `architecture/open-decisions.adoc`).**
  In this repository's own spine, even when a consumer needs it. A consumer's change names the
  toolkit change id, and the toolkit change names the consumer need it serves.

## Tools

- Run everything through `make` (Python through uv); never bare `python`/`pytest`.
- **One tool per question.** Outline of a file or a symbol's body: Serena's `serena_repl` tool
  with `s.lsp.get_symbols_overview` / `s.lsp.find_symbol` (with the body), not `Read` on a whole
  file. Who calls it: `s.lsp.find_referencing_symbols`. Replace or add a whole function:
  `s.edit.replace_symbol_body` / `s.edit.insert_after_symbol`. One code shape in many files:
  `ast-grep run -p '<pattern>' --lang python` (look at the matches, then add `-r '<rewrite>' -U`).
  Text in docs, YAML, AsciiDoc or the Makefile: Grep. Blast radius: GitNexus `impact` (repo
  `rdf-persistence`): the lead runs it as a gate (see Gates); reviewers may run it read-only;
  builders do not.
- **Serena limits.** Use only `s.lsp` and `s.edit`. Never `s.shell` (shell commands go through
  Bash, where the hooks and permissions apply) and never `s.mem`: Serena memories are not used
  (`.serena/` is git-ignored). Reviewers use only the read queries (`s.lsp.find_symbol`,
  `get_symbols_overview`, `find_referencing_symbols`, `find_declaration`, `find_implementations`)
  and read-only GitNexus queries; never `s.edit`, `s.lsp.rename_symbol`,
  `s.lsp.safe_delete_symbol` or GitNexus `rename`.
- **Edit in place** with the Edit tool or Serena; never rewrite files with Python heredocs or
  `sed -i`.
- Temporary files go in `temp/` (git-ignored), not `/tmp` or the session scratchpad.

## Branches, commits, PRs

- Default branch **`develop`**: the PR target and what consumers install. Branch off it; never
  commit to it. A release comes last, so nothing is committed after the tag.
- Commits and PRs follow **meaningfy-git-workflow**, with two additions: the body wraps at
  ~72 columns, and the Trace line also names the decisions implemented
  (`Refs: <change-id> <task> PD-24`, using the ids as the change's `design.md` spells them;
  outside a change, `Refs: #<issue>`). **No AI attribution**
  (`.claude/settings.json` enforces it for Claude Code).

## Delivery: what this repo adds to epic-delivery

- **Builders** are the `implementer` subagent. The epic-delivery skill (3.15.0 or later) sets who
  commits, who runs impact and the change check, and when gates are re-run; what this repo adds:
  - **Every brief** carries the standing rules (models, not dicts; LinkML is the single source;
    the testing checklist; the Tools section above) and overrides the implementer's own impact
    step: builders do not re-index or run impact, and the report's impact field reads "lead's
    check". The report names each make target run with its time and test count.
  - **Task gate**, one command: `make test-changed check-quality`, or
    `make test-fast check-quality` after changing `domain` or a port in `services`, or when unsure
    what the change reaches.
  - **Full gates:** `make check-all` and `make test-containers`, by the lead; never in a task.
    After the lead commits a schema change: `make check-generated`.
  - **Worktrees:** a separate worktree only for overlapping parallel work, or when another session
    holds this checkout.
- **Re-index GitNexus** at the start of each stage, and again before an impact check on symbols an
  earlier task of the stage added or moved: `gitnexus analyze --embeddings --skip-agents-md
  --skip-skills` (≈ 20 s). If it errors (developer, 2026-11-09), do not retry or investigate: run
  `gitnexus clean --force`, then `gitnexus analyze --embeddings --force --skip-agents-md
  --skip-skills` (≈ 4 min, in the background), then revert anything it wrote to `AGENTS.md`,
  `CLAUDE.md` or `.claude/skills/`.
- **Challenge, kept cheap (developer, 2026-11-09).** These override epic-delivery's review sets,
  and a brief cites this bullet as the authority: whichever lenses the appetite's review set runs,
  L1, L2 and L3 are never combined with each other, and L4 and L5 run as one pass; the adversarial
  tester runs right after the riskiest task (new invariants, write order, concurrency); the
  checker reads the lead's `make check-all` result and does not re-run tests.
- **Never poll:** a hook denies `sleep` loops in Bash; wait in the foreground, on a background
  notice, or with the Monitor tool.

## Docs

- `make check-docs`: no consumer terms in architecture pages, the package or the tests; every page
  in the nav; one mermaid version.
- Docs open with questions: add the question a new page answers to `questions.adoc`. Keep the
  durations table in `develop/index.adoc` from ordinary runs (no profiling).
- **Pages the developer revised (developer, 2026-11-10).** When the developer says they revised a
  page, add `:page-revised: <date> by the developer` under its `:description:` line, or move the
  date forward. Only the developer's word sets or moves it. List them with
  `grep -rl ':page-revised:' docs/`; what changed since is `git log --since=<date> -- <page>`.
