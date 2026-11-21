<!-- Secondary input, never groomed: GitHub issue #240 (meaningfy-ws/rdf-persistence), fetched 2026-11-21. The EPIC (../proposal.md) supersedes it. -->

# #240 Consumer validators on the writes of any aggregate root, not only the tenant root

## Summary

Let a consumer pass its own rules on the writes of **any** aggregate root of a tenant, not only of the tenant root. Today `install_service(..., root_validators=...)` runs the consumer's rules on the tenant root's create, replace and restore only; a rule on another root (a limit the schema cannot state) has nowhere to run on the generic API's writes.

## Context

Consumer: MWB2, change `v2-02-model-from-ea`, phase B (rdf-persistence lock `030f580f`, v0.8.0). Its UML model draws several `dct:hasPart` links from one root to collections of different kinds, each `0..1`. `rp-uml2linkml` reuses the toolkit's `has_part` slot for them (rule: a toolkit slot is reused by IRI; report line `toolkit-slot-kept ... multivalued false is not carried`), so the schema keeps one multivalued `uri` slot and the `0..1` limit per kind is lost. The consumer accepts that and wants to check the limit as its own rule on every write of that root, through the generic API.

## What is missing

`RootValidator` (`(old, new, principal) -> None`, raising `InvalidBody`) is run by `Tenancy` on the tenant root only. A `WriteGuard` sees every add and replace, but the guards are built by the kit (`WriteGuards(mapper, models, listings, workflows)`); a consumer cannot add one. So a consumer rule on a non-tenant root cannot run on `POST`/`PUT`/`PATCH` of the generic API without writing its own routes.

## Expected behaviour / proposed capability

A keyword `aggregate_validators` on `install_service` (and the kit), a mapping from a schema class name to the rules for its roots (a subclass's roots included):

```python
AggregateValidator = Callable[[BaseModel | None, BaseModel, Principal], Awaitable[None] | None]

install_service(
    app, schema=..., ...,
    aggregate_validators={"Shelf": [at_most_one_of_each_kind]},
)
```

```python
def at_most_one_of_each_kind(old: BaseModel | None, new: BaseModel, who: Principal) -> None:
    kinds = [kind_of(iri) for iri in new.has_part or []]
    if len(kinds) != len(set(kinds)):
        raise InvalidBody("A shelf holds at most one collection of each kind.")
```

If the rule needs to know the class of a referenced aggregate, an async form that receives the session (read-only use) is enough, e.g. `(old, new, principal, reader)` where `reader` reads a root's class by IRI.

Start-up refuses a class name that is not a root of the schema. A validator raises `InvalidBody`, answered `422` before anything is written, as for `root_validators`.

## Why it belongs in rdf-persistence

Any model-driven application has rules the schema cannot state (cross-slot limits, a limit per kind on a merged slot). The toolkit already has the pattern for the tenant root and for grants; extending it to every root keeps the generic API usable without per-application routes.

## Acceptance

- **Given** a validator registered for class `Shelf` that refuses two members of one kind **When** a client `POST`s a `Shelf` with two such members **Then** the answer is `422` with the validator's message and nothing is written.
- **Given** the same validator **When** a client `PATCH`es a stored `Shelf` into the refused shape **Then** the answer is `422` and the stored version is unchanged.
- **Given** a validator registered for a class name that is not a root **When** the service starts **Then** it refuses to start, naming the class.
- **Given** no validator for a class **When** it is written **Then** nothing changes from today.

## Impact on the consumer

MWB2's task "check the package's 0..1 collection limits as package rules" waits for this; the rest of the change goes on. MWB2 writes no route and no guard of its own meanwhile.

