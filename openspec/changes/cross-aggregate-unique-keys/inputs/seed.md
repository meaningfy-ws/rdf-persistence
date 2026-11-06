<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: unique keys across aggregates

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> *Unique keys across aggregates*, enforced at commit rather than checked before it.

From `docs/modules/ROOT/pages/architecture/index.adoc`, building blocks:

> |Unique keys across aggregates (e.g. a name unique within a kind)
> |deferred
> |v1 checks before the commit; two simultaneous writes can both pass.

## What the code does today (checked 2026-11-06)

- `unique_keys` is enforced inside one aggregate only: `generation/extensions/pydantic_validators.py`
  (a model validator on every class with a multivalued, object-valued slot whose range declares
  keys) and `generation/extensions/shacl_constraints.py` (a SPARQL constraint on the owning shape).
  The toolkit's own use is `Grant` in `model/rp_access.yaml`.
- The commit guard in `services/session.py` is `GRAPH $graph { $graph $p_version $old }` plus an
  `ASK` for the new token (PD-5).
- **Not confirmed:** the architecture says "v1 checks before the commit". No toolkit code checks a
  key across aggregates before a commit; such a check would be the application's own (for example a
  listing with an equality filter, `services/listing.py`). The race the seed names is real either way.

## Open questions for the developer

1. **How is the key declared?**
   - (a) LinkML's own `unique_keys` on the aggregate root class: standard LinkML; but v1 already
     gives `unique_keys` the in-aggregate meaning for owned classes, so a root's keys would mean
     "across aggregates" by position only.
   - (b) A toolkit annotation (for example `rp_unique_in_tenant: [slot, …]`): explicit, checked by
     the hard check; not standard LinkML.
2. **How does the commit enforce it?**
   - (a) A `FILTER NOT EXISTS` over all aggregate graphs of the type inside the guarded update:
     nothing new stored; the update scans the tenant, slower as it grows.
   - (b) A key index graph (for example `{tenant_iri}/keys`) holding one statement per key value,
     written in the same update: a cheap lookup; one more graph to keep in step, and the sweep and
     `remove` must clean it.
   - (c) A deterministic IRI minted from the key (a "claim" resource) that the conditional insert of
     `add_graph` already protects: reuses v1's add guard; ties identity to the key value.
3. **Scope of the key.** (a) per tenant and per aggregate type (the seed's "a name unique within a
   kind"); (b) also across several types sharing a parent class. (a) is simpler.
4. **Equality.** Exact lexical value, or normalised (case-folded, trimmed, language ignored)? Exact
   is predictable; normalised matches what users mean by "same name".
5. **Absent values.** Do aggregates without the key value conflict with each other? (a) no, absent
   never conflicts (as SQL `UNIQUE` with NULL); (b) yes, as v1's in-aggregate validators do.
6. **Problem response.** 409 (like a stale write) or 422 (like an invalid body)? 409 says "retry
   after reading"; 422 says "change your input", which is closer to a key conflict.
7. **Existing data.** When a key is added to a type that already has duplicates, does generation or
   start-up refuse, warn, or ignore? (Overlaps `schema-migrations`.)

## Developer answers (2026-11-06)

Developer: "choose what is best". Leader's choice (2026-11-06), answering Q-2:
- A guard inside the commit's own SPARQL update: it writes only if no other aggregate of the scope
  holds the key value. Fuseki runs each update in one write transaction, so two concurrent commits
  cannot both pass, and no extra data is stored.
- For a store that cannot run one update atomically, the `second-store` capability descriptor
  says so, and the toolkit documents the race instead.
- Still open: Q-1 and Q-3 to Q-7. Recommendations to propose: declare the key in LinkML
  (`unique_keys` plus an annotation for the scope); per tenant and per type; exact match; absent
  values never conflict; 409; generation reports existing duplicates.

## Test scenarios the EPIC must prove

- Two concurrent creates with the same key: exactly one succeeds (run many times, on Fuseki).
- A replace that keeps its own key succeeds; one that takes another aggregate's key is refused.
- A removed aggregate frees its key for a new one.
- The same key value in two tenants is allowed.
- The refusal is a problem response with a documented type, on the router and in the unit of work.
- An invalid declaration (unknown slot, a slot of an owned part) fails generation.
- In-aggregate `unique_keys` behave as in v1.
