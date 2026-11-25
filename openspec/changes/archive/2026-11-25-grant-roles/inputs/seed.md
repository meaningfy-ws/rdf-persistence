# Seeds (secondary, never groomed): issues #307, #310, verbatim, read 2026-11-24

## #307 Question: can a schema migration rewrite or drop grants naming a removed role?

## Summary

Question: can a schema migration rewrite or drop tenant grants? Roles are data converted from the UML model, so a model round can rename or drop a role that existing grants still name.

## Context

Consumer: MWB2, change `v2-06-roles-and-workflow` (rdf-persistence v0.9.0). Its decision for that case: an EA round that drops or renames a role ships a migration for the grants that name it. `howto/migrate.adoc` mentions grants only in the context of a restore; nothing says whether a schema migration may change them.

## What is asked

- Can a migration step rewrite grants (rename a role in every grant), or drop grants naming a removed role?
- If not, what is the intended path when a role disappears from the role definitions while grants name it? Today such a tenant's grants no longer validate, so any later `PUT …/grants` is refused.

## Impact on the consumer

Until this is answered, MWB2 holds back any model round that drops or renames a role (`v2-06-roles-and-workflow` RISK-2, finding T-2).


## #310 Public call for the roles the caller holds on an aggregate

## Summary

There is no public way to ask which roles the caller holds on a given aggregate (tenant grants, grants on the aggregate, system token roles combined).

## Context

Consumer: MWB2, change `v2-06-discussion` (rdf-persistence v0.9.0). When a member writes a comment with an audience of roles they do not hold, the toolkit hides the comment from them as well. MWB2's Web App warns before posting, and to do so it restates the toolkit's rule from the caller's tenant grants. That copy can drift from the toolkit's own decision (aggregate grants, token roles).

## Expected behaviour / proposed capability

A public call, e.g. `Collaboration.roles_held(iri)` or `kit.rules.roles(principal, iri)` documented for this use, returning the role names that count for the caller on that aggregate, by the same rule the audience check uses.

## Impact on the consumer

Not blocking: MWB2's warning is advisory, and visibility stays the toolkit's decision (`v2-06-discussion` P-3, finding T-1).


