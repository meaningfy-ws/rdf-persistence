# Design: slot-resolution

EPIC: `proposal.md` (#277, #278). Recorded after delivery (PR #289); the decisions below are the
ones the PR logged, numbered as there.

## Root causes

- **#277.** The stock gen-shacl gives every induced slot a property shape on its `slot_uri`,
  including the identifier slot. The identifier slot is `id` (`dcterms:identifier`, range `uri`), so
  its shape carries `sh:nodeKind sh:IRI`. A business slot on the same property then gets a second
  property shape, and a literal fails the first. Separately, the lock diff keyed a class's slots by
  IRI in a dict, so two slots on one IRI collapsed into one, and adding the business slot read as
  "range changed from anyURI to string".
- **#278.** LinkML keeps one slot per name across the import closure. `SchemaView` lets the last
  schema of the closure win, and `merge_imports` (the JSON-LD context's path) lets the first win.
  An application slot and a toolkit slot with the same name therefore resolved differently per
  reader and per import order. Reproduced: the view gave `dcat:version` and the merged schema gave
  `rp:version`.

## Decisions (delivery)

- **D-1 (DEC-1).** The identifier is the node's IRI and never a statement. Its property shape goes;
  the node keeps `sh:nodeKind sh:IRI` (`extensions/shacl.py`, `_require_iri_nodes`). Referrer naming
  skips it (`collaboration/services/referrer_naming.py`).
- **D-2 (DEC-2).** `schema.prefer_application_slots` finds each application slot whose name is a
  toolkit slot's under another IRI (`slot_name_clashes`). When no toolkit class carries that
  toolkit slot (`toolkit_carriers`: its `slots` or `slot_usage`), the slot leaves a deep copy of the
  toolkit module in the view. The loaded module is never mutated. A carried one stays, and the hard
  rule `toolkit_slot_name` refuses the clash, naming both slots, their IRIs and the carrying classes.
- **D-3.** A toolkit module is one whose source file lies under the package's `model/` folder
  (`is_toolkit_module`). The library still never names the generator. A module with no source file
  counts as the application's.
- **D-4.** The identifier's property shape is found by `sh:order`, which the stock generator numbers
  by induced slot from 0 with no gaps. Ceiling: if gen-shacl stops numbering this way, the #277 test
  fails and the lookup moves to another key.
- **D-5.** `test_no_bookkeeping_slot_is_in_any_schema` checked bookkeeping by bare name. It now
  checks the slot the name resolves to, the assumption #278 removes.
- **D-6.** GitNexus rates `load_schema` CRITICAL by fan-out (18 direct callers, 344 in all). The new
  behaviour applies only to a view with a name clash. Every regenerated toolkit artefact was
  unchanged apart from the intended shape edits (the `id` property shapes go), and every suite was
  green. The rating was flagged to the developer in the PR.
- **D-7.** The lock pairs the slots of one IRI: unchanged ones first, the rest in lock order; an
  unpaired old slot is removed, an unpaired new one added (`lock.py`, `_class_slot_changes`).
- Closed shapes ignore the session's predicates by IRI (`vocabulary.BOOKKEEPING_PREDICATES`), not
  by whatever the name `version` resolves to.

## Test cases

| Id | Test | Tier |
|---|---|---|
| TC-1 | `tests/unit/api/test_slot_resolution.py`: body to triples to shapes, mapper round trip, JSON representation, referrer naming | unit |
| TC-2 | `tests/unit/schema/test_slot_name_resolution.py`: the issue's two-module case in both import orders; a carried slot stays; the metamodel keeps `rp:version` | unit |
| TC-3 | `test_ext_shacl.py`: the identifier gives no property shape; Template's `version` is on `dcat:version` | generator unit |
| TC-4 | `test_lock.py::test_a_second_slot_on_an_iri_already_locked_is_an_added_slot` | generator unit |
| TC-5 | `test_hard_check.py`: the planted `toolkit_slot_name` fault (an application `graph`) | generator unit |
| TC-6 | `test_openapi_components.py`: Template's own `version` is served; no bookkeeping slot is | generator unit |

## Review

One L2+L3 pass (P-0005), nothing blocking. Taken: the rule is listed in
`architecture/generation.adoc`, and TC-2 pins that a carried slot never gives way. Left as minor:
the `not carriers` guard in `_slot_name_problems` is defensive for a view not opened through
`load_schema`; two toolkit modules defining one slot name would collide in `slot_name_clashes`,
which none does; two same-IRI slots that differ only in `required` pair by position in the lock.

## Gates

After the rebase on develop `4addd42e`: `make check-all` passed, `make test-containers` 352 passed,
CI 17 passed and 1 skipped.
