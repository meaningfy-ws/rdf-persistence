# Docs owed: cross-aggregate-unique-keys

> Derives from: EPIC `cross-aggregate-unique-keys` (proposal.md); tasks.md 2.3.

Decided at the close (leader, 2026-11-14): **no docs owed.** The EPIC changed user-facing
behaviour (a declared key, `KeyConflict`, the 409 `key-conflict` problem, the duplicates report),
and its PLAN carried the docs as task 2.3, delivered in #97:

| Page | What it says |
|---|---|
| `architecture/index.adoc` | The building block "Unique keys across aggregates" is delivered; the `Session` row names the key guards |
| `architecture/generation.adoc` | Scoped keys beside the `unique_keys` rows; the hard-check list |
| `architecture/api.adoc` | The `key-conflict` problem |
| `howto/adopt.adoc` | Declaring a key (`#model`); what `KeyConflict` guarantees and what is a diagnosis (`#key-conflict`); adding a key to live data (`#key-on-live-data`) |
| `questions.adoc` | "Can two aggregates share a key value?" |

A cold reader tested the two how-to sections (design.md D-8); `make check-docs` and
`make check-diagrams` passed on the merged head.
