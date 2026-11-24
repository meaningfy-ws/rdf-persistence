# Seeds: generator-module-cycles (secondary; never groomed)

The EPIC (`proposal.md`) supersedes these seeds; they are kept verbatim as evidence of how it was
shaped. Read with `gh issue view <n> -R meaningfy-ws/rdf-persistence --comments` on 2026-11-22.
Neither issue had comments or labels.

The scope note of the planning brief (the lead, 2026-11-22): seeds #208, and #206 only if it fits
the same appetite (decide and justify); area: the generator core (`rdf_persistence_generation/`);
include what the UML converter (`rdf_persistence_generation/uml/`) can stop doing once import cycles
load (today it merges packages that import each other into one module) and plan removing that
workaround with its tests; a separate EPIC, `converter-hardening` (#258-#261, #229), is planned in
parallel on the converter: name any overlap as a dependency or rabbit-hole and keep the
merge-removal here.

---

## #208 generator: split pydantic modules fail on module import cycles (OPEN)

## Problem

Two `module_kind: domain` LinkML modules that import each other pass
`rp-generate` (exit 0), but the generated Python package does not import:
the split pydantic modules (`extensions/pydantic_split.py`) write a plain
`from .<other> import <Class>` at module level, so each module waits for
the other.

```
app_books.py:35   from .app_shelves import Shelf
app_shelves.py:35 from .app_books import Book
ImportError: cannot import name 'Book' from partially initialized module ... (circular import)
```

## Reproduction

`tests/generator/integration/test_module_import_cycle.py` on branch
`feat/uml-to-linkml` (strict xfail; a second test shows the same classes
in one module generate and import).

## Why it matters

A UML model often has packages that refer to each other. Until this is
fixed, `rp-uml2linkml` writes the packages of each import cycle as one
module (uml-to-linkml PD-27, D-5).

## Possible fixes

- import the other module's classes lazily (`TYPE_CHECKING` plus
  `model_rebuild()` once the package is loaded);
- or one Python module per strongly connected component of the schema
  imports.

When fixed, the strict xfail turns red; then the converter can drop the
merge (PD-14's first branch).

Refs: #196

(No comments.)

---

## #206 generator: refuse two slots that share one slot_uri (OPEN)

## Problem

An application model can declare its own slot with the same
`slot_uri` as a toolkit slot, for example `slot_uri: dcterms:hasPart`
beside the toolkit's `has_part` slot. Two JSON-LD terms then map to one
IRI, so compaction picks one of them, and on a collection class two
slots would share the membership predicate.

## Proposal

`rp-generate` checks the combined schema (toolkit + application) and
refuses, naming both slots, when two slots resolve to the same IRI.

## Context

Follow-up of `collection-has-part` (#199), RISK-2: that change moves
membership to `dct:hasPart` and its how-to tells applications to reuse
`has_part`; the generator check was left out of its appetite.

(No comments.)

---

## Neighbouring issues read for overlap (not seeds)

- #229 uml-to-linkml hardening, the review's floor. Its *Structure* list says "the import-graph
  code sits in `convert.py`" and "annotation names and values (`module_kind`, `domain`, ...) are
  written as strings", both in code this EPIC edits (`_merge`, `_module_graph`, `_settle`,
  `_module_kinds`).
- #258 roles file encoding, #259 whole-model workflow check, #260 a reference collection's role to
  its own class, #261 service-start docs: no code this EPIC touches.
- #242 (closed by the import check): `rp-generate` imports and type-checks what it writes; the
  cycle test's first case asserts that check today.
