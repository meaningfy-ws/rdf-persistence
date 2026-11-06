<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: OpenFGA and property- or triple-level access

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> … *OpenFGA* as the decision engine, and property- or triple-level access.

From `docs/modules/ROOT/pages/architecture/open-decisions.adoc`, D-4:

> *A*: our own ODRL specification in RDF and our own evaluation. *OpenFGA deferred*, unless a cheap
> opportunity to reuse it appears.

From `docs/modules/ROOT/pages/architecture/access-control.adoc`:

> *OpenFGA is deferred*, unless a cheap opportunity to reuse it appears (for example a need for access
> that flows through relationships). The policy data is shaped so it can be compiled to OpenFGA then,
> without a migration.

> * Constraints map only partly (to CEL conditions); prohibitions have no direct counterpart (only
>   `but not`).
> * Prior work compiles ODRL to OpenFGA (Plaza-Ortiz et al., 2025); no code is published.

From the archived `toolkit-v1-foundation/proposal.md`, No-gos: "GraphQL (the API's backup option C),
OpenFGA, and property- or triple-level access: all deferred by the architecture."

Note: `open-decisions.adoc` records the developer's request for "fine-grained access in this
iteration"; v1 delivered it as per-tenant and per-aggregate access (D-4, option A).

## What the code does today (checked 2026-11-06)

- `rdf_persistence/services/access.py`: `AccessRules.require` decides per tenant and per aggregate;
  `load_caller_access` reads a caller's grants and prohibitions in one query.
- `rdf_persistence/entrypoints/auth.py`: `Gate.check`, one dependency per route action.
- `rdf_persistence/model/rp_access.yaml`: `Grant`, `Prohibition`, `RoleDefinition`, `Action`,
  `RoleLevel`; no property or statement target.

## Open questions for the developer

0. **Is OpenFGA wanted now?** D-4 lets it in only on "a cheap opportunity". Has one appeared (a need
   for access through relationships, a shared OpenFGA in the deployment)? If not, the OpenFGA stage
   is dropped and the EPIC shrinks to property-level access. Reopening D-4 is the developer's call.
1. **Stages and order.**
   - (a) Property-level access first (own check), then OpenFGA, then triple level.
   - (b) OpenFGA first (engine swap behind a port, same decisions), then property level on top.
   - (c) Property level only; OpenFGA and triple level stay deferred.
   (a) delivers visible value first; (b) avoids building property rules twice if OpenFGA will own them.
2. **Property level or triple level?** Property level names a slot of a class; triple level names
   individual statements (needs RDF-star, reification or a named graph per protected statement).
   Is triple level needed at all, or is property level enough?
3. **How is a protected property declared?**
   - (a) In the consumer's access module, as ODRL Permissions whose target is a slot IRI.
   - (b) As a schema annotation on the slot (for example `rp_read_role: librarian`): simple, but puts
     access in the domain module, against the access-module rule.
4. **Write semantics for hidden slots.** On a replace by a caller who cannot see a slot: (a) keep the
   stored value (merge); (b) refuse unless the body omits it; (c) treat the omission as removal and
   refuse. (a) is friendliest; it makes a replace no longer a pure replace.
5. **Versions and ETags.** Does a change to a hidden property change the version a reader sees? If so,
   readers learn that something hidden changed; a per-view version costs more.
6. **OpenFGA deployment.** Tuples kept in step by the commit (a write per grant change) or compiled
   at start-up from the access records? One OpenFGA store per deployment or per tenant?
7. **Relationship-based access.** If OpenFGA comes, is "access through relationships" (a reader of a
   library reads its books' scans) part of this EPIC, or only parity with v1?

## Developer answers (2026-11-06)

Developer: "a, but b and c sound good for future".
- Answers Q-0 and Q-1: stage 1 is OpenFGA as the decision engine, still per aggregate (swap the
  engine, keep the model). Property level, then triple level, are later stages, kept in this EPIC's
  outline.
- This reopens D-4 ("OpenFGA only on a cheap opportunity") by the developer's choice.
- Still open: Q-2 to Q-7, for the later stages; Q-6 (deployment) for stage 1.

## Test scenarios the EPIC must prove

- A protected slot is absent from JSON, JSON-LD and Turtle for a caller without access; present for one with it.
- A listing filter on a protected slot is refused for a caller without access, and reveals nothing.
- A listing total does not change with hidden properties.
- A write to a protected slot by a caller without access is refused and stores nothing.
- A caller without access to a slot can still replace the rest of the aggregate (per Q-4).
- v1's permission matrix still passes unchanged.
- With OpenFGA configured: every cell of the permission matrix gets the same decision from both engines.
- With OpenFGA configured: a grant change is reflected in the next decision.
- 401, 403 and 404 still carry no detail; a hidden tenant and an absent one still look alike.
