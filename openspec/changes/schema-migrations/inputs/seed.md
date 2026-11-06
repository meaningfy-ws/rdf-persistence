<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: schema migrations

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> *A second store* (Oxigraph, Virtuoso) with a capability descriptor, and schema migrations.

From `docs/modules/ROOT/pages/architecture/index.adoc`, building blocks:

> |Annotation sets, forms from shapes, schema migrations, server-sent events |deferred |No v1 need.

From the archived `toolkit-v1-foundation/proposal.md`, No-gos: "… schema migrations, and forms from shapes."

## What the code does today (checked 2026-11-06)

- No schema version anywhere: `rdf_persistence/model/rp.yaml` and `tests/fixtures/library/*.yaml`
  declare no `version:`; nothing in `rdf_persistence/` reads one.
- `rdf_persistence/generation/manifest.py`: records the generated code's freshness, not the data's.
- Writes are validated with the shapes (PD-14); reads return the stored graph unvalidated.

## Open questions for the developer

1. **Where is the version recorded?**
   - (a) Per tenant, in its `meta` graph: one statement per tenant, migrations run per tenant.
   - (b) Per aggregate, about its graph IRI (with the tracking statements): fine-grained, allows
     lazy migration; one more statement per aggregate.
   - (c) In the tenant's access record in the system database: read with the access check already.
2. **How is a migration written?**
   - (a) SPARQL Update templates per version: fast, set-based, runs in the store; easy to get wrong
     on blank nodes and owned parts.
   - (b) Python over the generated models of the old and new schema (read with the old mapper,
     write with the new): typed and testable (models-not-dicts); needs both versions' generated code.
   - (c) Declarative (rename slot, move class) in a LinkML-adjacent file, compiled by the toolkit:
     least code per consumer; a new mini-language to own.
3. **When does it run?** (a) Eagerly at start-up, before serving (like the sweep); (b) by an
   operator's command; (c) lazily, per aggregate on read or write. (a) is simple and delays start-up;
   (c) never blocks, but old and new shapes coexist.
4. **What may a running service do with a tenant that is behind?** Refuse (503 or a problem type),
   serve read-only, or serve as is?
5. **Down-migrations?** Needed for rollback of a release, or is restore-from-backup the rollback?
6. **Version tokens.** Does a migrated aggregate get a new version (clients see a conflict) or keep
   its version (clients may overwrite migrated data with an old body)?
7. **The toolkit's own metamodel.** Are changes to `rp_*` modules (for example the access record)
   migrated by the same mechanism, shipped with the toolkit release?
8. **Version of what?** A version declared on the consumer's root schema (`version:` in LinkML), or
   a counter the toolkit derives from the migrations present?

## Developer answers (2026-11-06)

Developer: "migrations must be automated. I liked a lot how the Strapi CRM handles
migrations automatically. they have a good set of rules, get inspired from there as a principle and
apply them to graph DB schemas".
- Answers Q-2 and Q-3 in principle: migrations are automatic, and derived from the change between
  the stored schema version and the new LinkML schema.
- The rule set for which changes are safe to apply automatically (added classes and slots) and
  which need an explicit step (removals, renames, type changes) is modelled on Strapi's. Hand-written
  data migrations, ordered and recorded once applied, cover what a diff cannot infer.
- The planning step studies Strapi's rules from its documentation before fixing them here.
- Still open: Q-1, Q-4 to Q-8.

Developer: "accept recommendations, and continue" (2026-11-06).
- Accepted: migrations run automatically at start-up, before serving; a tenant whose data is behind the schema is refused until it is migrated.
- Every question still open: the leader drafts a recommendation when the PLAN is derived, and the developer accepted recommendations by default (2026-11-06). Each one is recorded in the PLAN as the leader's choice, and the developer may overrule it.

## Test scenarios the EPIC must prove

- A new tenant records the current schema version at creation.
- A renamed slot is migrated in every tenant; migrated aggregates validate with the new shapes.
- A second run of migrations does nothing (idempotent per tenant).
- A failing migration leaves its tenant at the previous data and version; other tenants migrate.
- A tenant behind the running schema is not served as if it were current (per Q-4).
- Two service instances starting at once do not run one migration twice (if eager).
- Owned parts (skolemised blank nodes) and loaded-graph registry entries survive a migration.
- A metamodel change shipped by the toolkit migrates the access records (if Q-7 says yes).
