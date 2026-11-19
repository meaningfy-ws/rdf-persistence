# Audit of the docs on develop at 06ee1a77 (lead, 2026-11-19)

Secondary input, never groomed.

## What exists (pages outside `background/`, lines)

| Page | Lines | Genre today | Finding |
|---|---|---|---|
| `index.adoc` | 14 | landing | stale: "developed inside the repository of its first consumer"; links only architecture and SOA |
| `questions.adoc` | 482 | FAQ hub | good entry point (AGENTS.md names it); links into `adopt` by anchor |
| `tutorials/getting-started.adoc` | 9 | placeholder | "to be written" |
| `user-guide/index.adoc` | 8 | placeholder | "to be written" |
| `reference/index.adoc` | 12 | placeholder | "to be written"; says reference pages should be generated |
| `requirements/index.adoc` | 6 | placeholder | "to be written"; the truth is `openspec/specs/` |
| `howto/adopt.adoc` | 2043 | tutorial + manual + reference | the whole user manual, 14 steps; 47 inbound anchor links |
| `howto/commits.adoc` | 196 | explanation | an explanation among how-tos |
| other `howto/*.adoc` (11) | 133–720 | how-to | sound; nav nests 8 under `adopt`, leaves 4 at top level |
| `architecture/index.adoc` | 361 | explanation | "Architecture v1": needs, C4, blocks, layering |
| `architecture/data-flows.adoc` | 1239 | explanation | where data lives, per operation |
| `architecture/generation.adoc` | 790 | explanation + reference | holds the metamodel description |
| `architecture/api.adoc`, `access-control.adoc` | 461, 298 | explanation | fine |
| `architecture/open-decisions.adoc` | 106 | decision log | D-1..D-n of 2026-11-05; apart from the ADRs |
| `adr/*` | 5 records + index | decision record | fine |
| `develop/index.adoc` | 279 | developer manual | library and generator mixed |
| `develop/testing.adoc`, `agents.adoc` | 130, 180 | guideline | fine |
| `background/soa/**` | 30 pages | research | keep as is |

## Specs

22 capabilities in `openspec/specs/` (`rp-*` and `soa-review`). No docs page lists them; no
use-case catalogue exists anywhere in the repository.

## Gaps against the request

- System specification: ADRs exist; use cases missing; capabilities not mapped; models described
  only inside `generation.adoc`.
- User manual: one monolith; no simple example; generator usage buried.
- Developer manual: library and generator in one page.
- How-tos: present, unevenly grouped, no index by capability.
- Background: present; keep.
- Checks: nav reachability and consumer terms are checked; links are checked by page only (by
  Antora at build), never by anchor.
