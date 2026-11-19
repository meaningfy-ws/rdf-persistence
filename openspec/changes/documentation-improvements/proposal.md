<!-- Parents: capability rp-developer-checks (the docs checks: every page in the nav, no consumer
     terms); AGENTS.md ("Docs: docs/ (Antora); start with questions.adoc"; "a new docs page adds the
     question it answers to questions.adoc"); the placeholders tutorials/getting-started,
     user-guide, reference and requirements, each promising a page that was never written.
     Seed: inputs/seed.md (the developer's request of 2026-11-19, verbatim) and inputs/audit.md
     (the lead's audit of the docs as they stood on develop at 06ee1a77). -->

# EPIC: Documentation improvements

> Shaped 2026-11-19 by the lead from the developer's request (inputs/seed.md). The developer asked
> for the structure to be proposed, planned and executed in one go, so every `DEC` below is the
> leader's choice and may be overruled; the open questions are in inputs/questions.md with the
> answer the lead assumed.

**Golden-thread parent:** capability `rp-developer-checks` and the developer's request: "propose a
clean/clear structure that addresses system architecture specifications (ADRs, UCs, capabilities
and features, models etc), user manuals (including a simple app example, and how to use not only
toolkit but also generators), developer manuals (library and generators), howtos and guidelines
(around each major capability/feature), keep in place the SOTA and background research".

## Appetite

**LARGE.** Every page outside the background study is touched (moved, relinked or retitled);
one 2043-line page is split into eleven; four placeholders are written; one small docs check and
one small reference generator are added. No library behaviour changes. One PR, committed in
stages.

## Why

The docs grew one change at a time and now read like that (inputs/audit.md):

- **Four placeholders** (getting started, user guide, reference, requirements) promise pages that
  were never written; a newcomer's first click lands on "to be written".
- **One page is the whole user manual.** `howto/adopt.adoc` is 2043 lines: install, modelling,
  the generator, the session, tenants, files, access, the service, tests and the IRI policy. 47
  links from elsewhere point into it by anchor.
- **No map from specification to docs.** The 22 `rp-*` capabilities in `openspec/specs/` are the
  truth, but no page lists them, says which use case each serves, or which page explains it. There
  is no use-case catalogue at all.
- **The generator has no manual of its own**: using `rp-generate` is buried in steps 3 to 7 of
  `adopt`, and changing it is two sections of the toolkit developer page.
- **Stale and mixed signals**: the landing page says the toolkit lives in its consumer's
  repository (it moved out); the nav nests some how-tos under "Build an application" and leaves
  others at top level; an explanation ("How commits and conflicts work") sits among the how-tos;
  the 2026-11-05 decisions page sits apart from the ADRs it led to.
- **Links are not checked by anchor.** Antora reports a missing page, not a missing `#anchor`, so
  a split would silently break links.

## Solution outline

Seven sections, each for one reader and one genre (Diátaxis), in this order in the nav:

```text
Introduction, Common questions            everyone: what it is, where to go
Tutorial: Getting started                 newcomer: one note stored and read back, end to end
User manual                               application developer, in the order they work:
  install and lay out · write the model · generate (the rp-generate manual) · use the generated
  classes and guard them · store and read · tenants · files · access · serve · test · IRI policy
How-to guides and guidelines              by capability: data (commits, keys, collections, ...),
                                          collaboration, events, schema change, operations
Architecture and specification            architect: overview, use cases, capabilities (rp-* map),
                                          models (metamodel, generated diagrams), data flows,
                                          generation, API, access, commits, ADRs, decision log,
                                          the state-of-the-art background study (unchanged)
Reference                                 look-up: public Python API, rp-generate CLI, settings
Developer manual                          toolkit developer: library, generator, testing, agents
```

The actors are the application developer (who also runs the application), the API client, the
system architect who reuses the toolkit in a platform of their own, and the toolkit developer
(developer, Q-8).

The getting-started example is a real, tested mini application kept as an Antora example; the
tutorial includes its code by tag, and a test generates and runs it, so the tutorial cannot rot.
A docs check fails on any `xref` whose page or anchor does not exist, which makes the split safe
and keeps it safe.

## Key decisions

- **DEC-1** (leader's choice): **the seven sections above**, one reader and one genre each.
  Rejected: keeping the four placeholders as top-level entries (they are the problem); a single
  "Guides" section mixing tutorial, manual and how-to (the genre mix is what makes `adopt` hard to
  read).
- **DEC-2** (leader's choice): **`howto/adopt.adoc` is split, not rewritten**, by its own numbered
  steps into `user-manual/*.adoc`, its text moved verbatim except for links. The old URL survives
  as a `page-aliases` entry of the user manual's index. Every link into it is rewritten to the new
  page and anchor. Each page is then polished to read as a page of its own, coherent and
  consistent with the others, keeping the explanations that are good (developer, Q-1). Rejected: rewriting the manual (out of appetite; the text is reviewed and
  correct); leaving it whole and adding a table of contents (the nav cannot show what one page
  holds).
- **DEC-3** (developer, 2026-11-19, re-shaped from the leader's first choice): **the tutorial's
  example is a minimal cut of the toy library** (`Library`, `LibraryAccess`, `Book`), kept under
  `docs/modules/ROOT/examples/getting-started/` so the page includes it by tag, run by a test in
  the generator's integration tier that also fails when its text differs from the toy's. The
  reader goes on into the user manual with the same domain. Re-shaped because the developer asked
  to reuse the toy rather than invent a second example (inputs/answers-2026-11-19.md, Q-2); the
  first cut, a separate notes application, was dropped. Rejected: untested snippets in the page
  (they rot at the first API change); the whole toy as the tutorial (six modules, too much for a
  first walk).
- **DEC-4** (leader's choice): **the specification pages summarise and link, never restate.**
  `requirements/use-cases.adoc` lists the actors and the use cases, each pointing at the
  capabilities that realise it; `requirements/capabilities.adoc` lists the 22 capabilities with
  their purpose and the pages that explain them. The SHALLs stay in `openspec/specs/`. Rejected:
  copying requirements into the docs (two truths).
- **DEC-5** (leader's choice): **the models page includes the generated Mermaid diagrams of the
  metamodel** (`rp-generate` writes them, `make generate` refreshes them), so the page follows the
  schema. If the diagrams do not render in the site, the page links the schemas instead and says
  so.
- **DEC-6** (leader's choice): **the public Python API reference and the `rp-generate` usage are
  generated** into Antora partials by `docs/tools/reference.py` from `__all__`, the docstrings and
  the CLI's argument parser; `make check-docs` fails when a partial is stale. Rejected: hand-written
  lists of 141 names (they drift).
- **DEC-7** (leader's choice): **a docs check resolves every `xref` and `<<anchor>>`** against the
  pages and their explicit and section ids, and runs in `make check-docs`.
- **DEC-8** (leader's choice): **explanations move to the architecture section**: "How commits and
  conflicts work" becomes `architecture/commits.adoc` (alias kept); the 2026-11-05 decisions page
  is listed under the ADRs as the decision log. Rejected: a separate "Concepts" section (one more
  place to look, for one page).
- **DEC-9** (leader's choice): **the developer manual splits by package**: `develop/index.adoc`
  keeps the library, `develop/generator.adoc` takes the generator's sections (extensions, check
  rules, the generation loop). The root `README.md`, `INSTALL.md` and `CONTRIBUTING.md` stay as
  the repository's entry points and link to the docs instead of repeating them.

## Rabbit-holes

- **Rewriting prose.** Tempting while moving it. Only links, titles and the stale landing text
  change; a passage that is wrong is listed in the handover, not fixed here.
- **Anchor ids.** Asciidoctor gives a section without an explicit id the id `_title_words`; the
  check must compute the same ids or it reports false breaks.
- **Diagrams of a large metamodel** may be unreadable or slow to render; DEC-5's fallback applies.

## No-gos

- No change to the background study (`background/soa/`), beyond its nav label.
- No change to `openspec/specs/` requirements, other than the docs-check delta of this change.
- No library or generator behaviour change; the only code is the docs check, the reference
  generator and the example application with its test.
- No new docs toolchain (Antora stays, with its current UI and mermaid pin).
- No hosting or publishing work.

---

## What Changes

- New pages: tutorial (getting started), user manual (11 pages from `adopt`), how-to index,
  use cases, capabilities, models, reference (API, CLI), generator developer manual.
- Removed placeholders: `user-guide/index.adoc`, `reference` and `requirements` placeholders
  replaced by real pages.
- Moved: `howto/adopt.adoc` → `user-manual/`, `howto/commits.adoc` → `architecture/commits.adoc`
  (aliases kept).
- `docs/tools/check_docs.py` resolves xrefs and anchors; `docs/tools/reference.py` writes the
  reference partials.
- The example application under `docs/modules/ROOT/examples/getting-started/` and its test.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-developer-checks`: the docs check also resolves every link and anchor, and fails on a stale
  generated reference.

## Impact

Docs only, plus `docs/tools/`, one test and the `Makefile`'s `check-docs`. Old page URLs keep
working through aliases; deep links to `howto/adopt.adoc#anchor` from outside the site lose their
anchor.
