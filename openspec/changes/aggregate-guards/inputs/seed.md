# Seeds (secondary, never groomed): issues #305, #309, verbatim, read 2026-11-24

## #305 Aggregate validators: read slot values of a referenced aggregate

## Summary

An aggregate validator should be able to read named slot values of an aggregate it references, under the writer's access. Today the `AggregateReader` a rule receives offers only `classes_of(iri)`.

## Context

Consumer: MWB2, change `v2-07-package-editor` (rdf-persistence v0.9.0). A `MappingPackage` points to a minimum and a maximum `SourceVersion`, each its own root. The rule "minimum ≤ maximum" compares the two versions' `version_number` values, and the schema cannot state it. #240 gave consumer validators on any root, but the rule cannot see the numbers.

## What is missing

`AggregateReader` (`rdf_persistence/collaboration/services/aggregate_validators.py`) answers which classes an IRI has (empty if the IRI is missing or not readable). It cannot answer the value of a slot of that aggregate.

## Expected behaviour / proposed capability

A read on the reader, for example `values(iri, slot) -> list[...]` or `get(iri, slots=[...])`. It applies the writer's access (nothing for an aggregate the writer may not read) and runs inside the write's transaction, like `classes_of`.

## Why it belongs in rdf-persistence

Any model-driven application has cross-aggregate rules over referenced values: ranges, ordering, compatibility. A consumer cannot run them on the generic API's writes without the toolkit handing it the values.

## Acceptance

- A rule registered for class A can read a slot of a root B that A references, within the same transaction as the write.
- A B the writer may not read yields nothing.
- Existing rules using `classes_of` are unchanged.

## Impact on the consumer

MWB2 checks the order of a package's source range in its Web App only until this lands (`v2-07-package-editor` DEC-2, P-4). A request sent straight to the API can store a reversed range.


## #309 Aggregate validators do not run on delete: a consumer delete guard

## Summary

Question / request: aggregate validators run on create, replace and patch (the write guard, `write_guards.py` at v0.9.0), not on delete. A consumer rule that should refuse deleting a root in some states has nowhere to run.

## Context

Consumer: MWB2, change `v2-06-conceptual-mapping` (rdf-persistence v0.9.0). A conceptual mapping under review (workflow state `for_review_*` or `approved`) may be edited only after it is moved back to `in_development`; the rule is an aggregate validator reading the root's own `workflow_status`. Deleting the same CM through the generic route skips that rule.

## Expected behaviour / proposed capability

Either aggregate validators also see a delete (old aggregate, no new one), or a separate consumer delete guard keyed by class, in the same transaction as the delete.

## Impact on the consumer

MWB2 offers Delete in its Web App only while a CM is editable; the API still allows it (`v2-06-conceptual-mapping` finding T-2, an accepted gap until this is answered).


