Parent EPIC: documentation-improvements (proposal.md)

# Tasks

Appetite LARGE, one PR. Gate per stage: `make check-docs` plus the stage's own check; at the end
`make test-changed check-quality`, `make check-diagrams`, `make build-docs`.

## Stage 1: the safety net (DEC-7)

- [x] 1.1 Test first: unit tests for the section-id function and for a broken xref, a broken
      anchor, a broken `<<id>>` and an alias (spec delta "Every docs link resolves").
- [x] 1.2 `check_links()` in `docs/tools/check_docs.py`; develop's docs passed unchanged.

## Stage 2: the example and the tutorial (DEC-3, re-shaped)

- [x] 2.1 Test first: `tests/generator/integration/test_getting_started_example.py` (runs the
      example; fails when its text differs from the toy's).
- [x] 2.2 The minimal cut of the toy library under `docs/modules/ROOT/examples/getting-started/`.
- [x] 2.3 `tutorials/getting-started.adoc` written from it.

## Stage 3: the user manual (DEC-2)

- [x] 3.1 Split `howto/adopt.adoc` into `user-manual/*.adoc`; links rewritten.
- [x] 3.2 `user-manual/index.adoc` with the steps and the aliases; `user-guide` placeholder removed.
- [x] 3.3 Each page polished (developer, Q-1); the tests that run the manual's code
      (`test_adopt_validators`, `test_adopt_step6`, `test_old_paths_gone`) follow the new pages.

## Stage 4: architecture and specification (DEC-4, DEC-5, DEC-8)

- [x] 4.1 `howto/commits.adoc` → `architecture/commits.adoc` with its alias.
- [x] 4.2 `requirements/use-cases.adoc` (the developer's four actors, Q-8) and
      `requirements/capabilities.adoc`.
- [x] 4.3 `architecture/models.adoc` with the metamodel's generated diagrams (they render).
- [x] 4.4 ADR index links the decision log; the background study sits in the architecture
      section (Q-7); the overview has a "Fit and limits for a platform" section.

## Stage 5: reference (DEC-6)

- [x] 5.1 Test first: `tests/unit/test_docs_reference.py`.
- [x] 5.2 `docs/tools/reference.py`, `make docs-reference`, the check in `make check-docs`.
- [x] 5.3 `reference/index.adoc`.

## Stage 6: developer manual and how-tos (DEC-9)

- [x] 6.1 `develop/generator.adoc` from the generator sections of `develop/index.adoc`.
- [x] 6.2 `howto/index.adoc`: guides by capability.
- [x] 6.3 Root `README.md`, `INSTALL.md`, `CONTRIBUTING.md` are entry points into the docs.

## Stage 7: landing, nav, questions

- [x] 7.1 `index.adoc` rewritten.
- [x] 7.2 `nav.adoc` in the target order and labels.
- [x] 7.3 `questions.adoc`: a question for each new page.
- [x] 7.4 Gates run; a cold reader reviewed three reading paths (14 findings, fixed); what is left
      is in `handover.md`.
