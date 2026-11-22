<!-- PLAN (design half) of tenant-root-owned-parts. PLAN = this file + tasks.md. Retrospective. -->

# Design: tenant-root-owned-parts

> Derives from: EPIC `tenant-root-owned-parts` (`proposal.md`, issue #276), DEC-1 to DEC-4.

## Context

- `Tenancy.create(label, root_slots, creator)` built the root with
  `root_class.model_validate({**root_slots, label, id: tenant})`. An owned part's class mixes in
  `Described`, so its `id` is required. Nothing on this path minted one.
- The generic create (`Documents._settled`) names each blank-node part with
  `Iris.mint_part(tenant, root, type)` while it settles the JSON-LD graph. The root's PUT goes
  through that path, so it was never affected.

## Decisions

- **PD-1 (DEC-3):** `Tenancy._with_part_iris(class_name, slots, tenant)` walks the induced slots
  of the class. For each slot that `holds_owned_part` and that is present under its `json_name`, it
  replaces each part object with `_part_with_iri`. That method recurses into the part's own slots,
  then adds `id = mint_part(tenant, root=tenant, iri_type_of(range class))` when the part's class
  has an identifier slot. A value that is not an object is left to the root's validation.
- **PD-2 (DEC-1):** `_part_with_iri` raises `InvalidBody` when a part names `id`, before minting.
- **PD-3 (DEC-2):** the type is the slot's range, with no body type input.
- **PD-4 (DEC-4):** the toy `Library` gains `charter` (optional, inlined, `owned: true`, range
  `Charter`, mixin `Described`). It is optional so that every existing tenant fixture stays valid;
  the 422 is the same as for a required part.

## Verification

- Unit, `tests/unit/api/test_tenant_root_parts.py`, through the toy service's routes:
  - create with a part → 201, part IRI under `{tenant}/parts/`;
  - root PUT with a new part → 200, minted;
  - create with a part `id` → 422.

  The first and third failed before the fix; the first failed with the issue's exact message.
- Full gates: `make check-all` (after the rebase) and `make test-containers` (351 passed).
