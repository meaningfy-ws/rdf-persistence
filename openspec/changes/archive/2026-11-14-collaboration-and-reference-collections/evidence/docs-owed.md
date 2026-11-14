# Docs owed: collaboration-and-reference-collections

> Derives from: EPIC `collaboration-and-reference-collections` (proposal.md, "As built"); the
> stage 4 structure review (design.md PD-32, "For the docs stage").

Decided by the lead, 2026-11-14: **docs are owed.** The EPIC added four use cases and changed
user-facing behaviour (a new action, a toolkit-owned state, deletes that take comments and
records, generic routes that answer only for their own class). Each stage wrote its how-to page,
tested by a cold reader; those are current. What is behind is the architecture section, which
describes the toolkit as it was before this EPIC, and one page states something false.

## Pages

| Page | Genre | What it needs | Reader |
|---|---|---|---|
| `architecture/generation.adoc` | Reference (maintainers) | The metamodel's module diagram shows six modules; there are nine (`rp_collections`, `rp_discussion`, `rp_workflow`, with `rp_workflow → rp_discussion`). The list of hard checks lacks `RESERVED_SEGMENT` (the `rp-` prefix) and `WORKFLOW`. The annotations table lacks `workflow` and the `toolkit` value of `rp_writes` | Maintainers; modellers |
| `architecture/index.adoc` | Explanation (C4) | The component diagram has no collaboration component (the public face, with reference collections, discussion, transitions, workflows behind it) and no write guards. The public API table lacks `kit.collaboration`, `kit.workflows`, `install_service(workflows=…)`, `Collaboration`, `Workflows`, `InvalidWorkflow` and the new exported models. The `model/` row lists six modules | Maintainers; adopters |
| `architecture/access-control.adoc` | Explanation | A short section on what this EPIC added to access: `annotate` (it implies `read`, is not `modify`); how a comment's audience is matched (role names; a token role only if defined at system level); how a transition is permitted (the roles on the edge, not `modify`; `read` needed; a Prohibition of `modify` freezes; a Prohibition of `annotate` refuses its comment; the edge is checked before the role); that hidden things are counted, never named, and where they are not even counted (rule members) | Maintainers; adopters |
| `architecture/data-flows.adoc` | Explanation | The request of a transition: one update with the replace that carries the new state, the record and the optional comment, guarded by the version token (the state allowance is not in the request: the transaction hands it to the write guards); and the three private guards of a transaction side by side (match, presence, state allowance) with who may use each. The write guards and the dependents drop are already there | Maintainers |
| `questions.adoc` | Questions | Check that the four questions added by the stages still point at the right anchors; add "Why does my delete take comments and history with it?" if the delete section of the how-to pages does not already answer it under a question | Everyone |

Not owed: the four how-to pages (`reverse-references`, `reference-collections`, `discussion`,
`workflow`), the adoption guide's `workflows=` paragraph and the durations table, all written and
reviewed in their stages.

## How it runs

Per D-11, before the verdict (the archive still waits for it): the lead loads `technical-writing`; one
writer revises the pages above from the code and the "As built" table; `make check-docs` and
`make check-diagrams`; one PR into `develop` with the doc lens (L2 doc agreement) and the
structure lens (L3: the pages must describe the structure truthfully). Then the archive.
