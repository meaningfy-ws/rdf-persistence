Parent EPIC: documentation-improvements (proposal.md)

# Tasks

Appetite LARGE, one PR, one commit per stage. Gate per stage: `make check-docs` plus the stage's
own check; at the end `make test-changed check-quality`, `make check-diagrams`, `make build-docs`.

## Stage 1: the safety net (DEC-7)

- [ ] 1.1 Test first: unit tests for the section-id function and for a broken xref, a broken
      anchor, a broken `<<id>>` and an alias (spec delta "Every docs link resolves").
- [ ] 1.2 `check_links()` in `docs/tools/check_docs.py`; run it on develop's docs and fix any link
      already broken (each fix listed in the commit body).

## Stage 2: the example and the tutorial (DEC-3)

- [ ] 2.1 Test first: `tests/generator/integration/test_getting_started_example.py`.
- [ ] 2.2 The notes app under `docs/modules/ROOT/examples/getting-started/`, tagged for include.
- [ ] 2.3 `tutorials/getting-started.adoc` written from it.

## Stage 3: the user manual (DEC-2)

- [ ] 3.1 Split `howto/adopt.adoc` into `user-manual/*.adoc` by the design's mapping; rewrite links.
- [ ] 3.2 `user-manual/index.adoc` with the order of work and the aliases; delete the
      `user-guide` placeholder.
- [ ] 3.3 `make check-docs` green.

## Stage 4: architecture and specification (DEC-4, DEC-5, DEC-8)

- [ ] 4.1 Move `howto/commits.adoc` to `architecture/commits.adoc` with its alias.
- [ ] 4.2 `requirements/use-cases.adoc` and `requirements/capabilities.adoc` (alias for the old
      placeholder).
- [ ] 4.3 `architecture/models.adoc`, with the metamodel's generated diagrams (or DEC-5's fallback).
- [ ] 4.4 ADR index links the decision log.

## Stage 5: reference (DEC-6)

- [ ] 5.1 Test first: `reference.py --check` fails on a stale partial (spec delta "The generated
      reference is fresh").
- [ ] 5.2 `docs/tools/reference.py`, `make docs-reference`, the call from `check-docs`.
- [ ] 5.3 `reference/index.adoc` includes the partials and links `howto/settings.adoc`.

## Stage 6: developer manual and how-tos (DEC-9)

- [ ] 6.1 `develop/generator.adoc` from the generator sections of `develop/index.adoc`.
- [ ] 6.2 `howto/index.adoc`: guides by capability.
- [ ] 6.3 Root `README.md` "Documentation" section points at the sections.

## Stage 7: landing, nav, questions

- [ ] 7.1 `index.adoc` rewritten (no stale extraction sentence; one line per section and reader).
- [ ] 7.2 `nav.adoc` in the target order and labels.
- [ ] 7.3 `questions.adoc`: each new page's question added (AGENTS.md rule).
- [ ] 7.4 Full gates; a cold reader reviews the tutorial and the landing page; findings fixed or
      listed in the PR.
