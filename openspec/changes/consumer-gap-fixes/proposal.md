<!-- Parents: issues #304, #306, #311, #312 (inputs/seed.md); openspec/specs/rp-uml-import,
     rp-tenancy, rp-service-api, rp-aggregate-store. Q&A: inputs/qa.md (2026-11-24).
     Serves (D-12): MWB2 v2-06 (one ontology collection per version needs #304's unique key;
     v2-06-roles-and-workflow P-3 / T-1 waits on #306; v2-06-discussion T-2 and v2-06-cm-review
     P-2 on #311; v2-06-coverage-and-checks §4.3 on #312). -->

# EPIC: Four consumer gaps: a narrowed role, grant roles, state_iri, and absence in find

## Appetite

**SMALL**, a bug-fix group (P-0020): four defects, each in one place, existing structure reused.
Four stages, one PR each, in the owner's priority: #304, #306, #311, #312. It starts after the
in-flight `domain-values-and-fixes` has merged its last PR (its order, DEC-9, is kept: inputs/qa.md).

## Why

- **#304.** A «root» subclass that redraws an inherited `0..*` role as `1` is converted without
  `multivalued: false`, so it inherits `multivalued: true` from its parent's `slot_usage` and
  `rp-generate` refuses a unique key over it. "Each B belongs to exactly one W, and at most one B
  per W" cannot be said.
- **#306.** `Tenancy.set_grants` stores a grant naming an undefined or system-level role; the
  generic `PUT …/grants` route refuses it. After one such write every later `PUT …/grants` for the
  tenant fails with `UnknownRole`.
- **#311.** `howto/workflow.adoc` imports `state_iri` from a submodule. A consumer that imports
  only the top level cannot follow it.
- **#312.** `find(cls, slot=None)` searches for the literal `"None"` and so matches nothing. Neither
  `find` nor the listing can ask for "no value for this slot", although unique keys already count
  an absent value (#202).

## Solution outline

- **A narrowed limit is written even when it is false.** The converter writes a class's
  `slot_usage` value for every limit on which the usages differ, `false` included, so a subclass's
  `1` overrides its parent's `0..*`.
- **One path for grants.** `Tenancy.set_grants` checks every role against the role definitions
  before the consumer's grant validators. The route stops checking on its own, so both paths
  refuse the same input the same way.
- **`state_iri` is public.** It is exported from the top level, and the how-to imports it from there.
- **Absence is a filter.** `find(cls, slot=None)` and the listing parameter `absent=<slot>` match
  the aggregates with no value for that slot. They combine with every other filter.

## Key decisions

- **DEC-1:** fix #304 in `usage_of` (the converter's one writer of a class's `slot_usage`): a
  differing boolean limit (`required`, `multivalued`) is written as `true` or `false`; an unset
  one is written as `false`. Rejected: writing `false` only when an ancestor's value is `true`.
  That needs an ancestor walk in a function that has none, only to save some explicit flags.
  `owned` keeps today's handling (No-gos).
- **DEC-2:** `Tenancy` takes `AccessRules` as a required constructor keyword. This is
  **BREAKING** for a consumer that builds `Tenancy` itself. `set_grants` calls
  `validate_grants(grants, tenant)` before the grant validators, and the route's own call goes
  (owner, round 2). Rejected: a `rules=` parameter per call, which a caller can still forget.
- **DEC-3:** `state_iri` joins `_LAZY_MODULES` and `__all__`, as #300 does for `expected_version`.
  Rejected: the how-to spelling out the IRI rule by hand (owner, round 2).
- **DEC-4:** in `find`, a `None` value means "no value for the slot". `None` inside a list, or
  `None` together with another value for the same slot, is refused (`ValueError`), because "absent
  and equal to x" never matches. `Contains` is unchanged.
- **DEC-5:** the listing spells absence as a repeatable reserved parameter, `absent=<slot>`
  (`?absent=filter_expression`). `absent` becomes reserved, as `sort`, `limit` and `offset` are.
  Rejected: an empty value `?slot=` (an empty string can be a stored value); `?slot!=` (reads as
  "not equal"); `?slot=null` (a string slot can hold "null"). This was decided by the planner at
  the round cap and is for the owner to review.
- **DEC-6:** one listing `Filter` carries absence: the services model gains `filter_absent`
  (boolean) next to `filter_contains`, and is regenerated with `make generate`. `find` and the
  listing build the same filter, so the query planner has one code path.
- **DEC-7:** four stages and four PRs into `develop`, in the order #304, #306, #311, #312. This
  EPIC lands with stage 1's PR. After the last merge a release is cut, so the consumer can move
  its lock (RISK-4).

## Rabbit-holes

- #304: the parent `A`'s own usage writes `multivalued: true` and `B is_a A` inherits it. Check
  with `SchemaView.induced_slot` that `B`'s explicit `false` wins, and not just the YAML text.
  The toy's other converter output must change only where usages differ (golden diff).
- #306: `validate_grants` raises `UnknownRole` / `InvalidGrant`, and `set_grants` documents
  `InvalidBody`. Keep the exception types the route maps today, so the HTTP answer does not change.
- #312: for a multivalued slot, absent means no triple for the slot's predicate at all. Count
  queries (`total_of`) must use the same pattern as the page query.
- `absent` as a reserved name takes a slot named `absent` out of the listing altogether (filter,
  sort, OpenAPI), as `sort` is today. Accepted; the listing docs say so.
- A slot with `ifabsent` is never absent in the store (the mapper writes its default), so absence
  never matches it. Documented, not changed.

## No-gos

- No other converter change, and no change to `owned`. Converter hardening stays in `converter-hardening`.
- No migration or clean-up of grants already stored (that is the access change, #307). No new
  grant validator API.
- No other top-level exports.
- No "not equal" or "present" filter, and no absence on `Contains`.
- No change to unique-key semantics (#202 already counts absence).

---

## What Changes

- Converter: a differing `required`/`multivalued` limit is written to `slot_usage` even when false.
  **BREAKING** for converted models where a subclass narrows an inherited multivalued role: the
  generated field becomes single-valued (RISK-1).
- Tenancy: `set_grants` validates roles. The route no longer validates on its own.
- Public API: `state_iri` at the top level.
- Persistence: `find(cls, slot=None)` and `?absent=<slot>` match an absent slot. **Behaviour
  change**: `None` used to match nothing (RISK-3).
- Services model: `Filter.filter_absent` and `Condition.filter_absent`. OpenAPI (built at
  runtime): the `absent` parameter on every listing.
- `Tenancy`'s constructor takes `rules` (**BREAKING** for direct constructors).
- Docs: `howto/workflow.adoc` (import), the listing reference (absence, reserved names), the
  tenancy how-to (a refused `set_grants`, RISK-2), CHANGELOG (RISK-1, RISK-3).

## Capabilities

### Modified Capabilities

- `rp-uml-import`: a narrowed inherited role keeps its narrowed multiplicity.
- `rp-tenancy`: `set_grants` refuses an undefined role as the route does.
- `rp-service-api`: `state_iri` is public; a listing filters on absence.
- `rp-aggregate-store`: `find` matches an absent slot.

## Impact

`rdf_persistence_generation/uml/slots.py`; `rdf_persistence/tenancy/services/tenancy.py`,
`rdf_persistence/api/entrypoints/kit.py` (wiring) and `router.py`; `rdf_persistence/__init__.py`;
`rdf_persistence/model/technical/persistence/rp_persistence_services.yaml` (regenerated),
`persistence/services/session.py`, `listing.py`, `core/domain/sparql.py`;
`api/entrypoints/openapi.py`; four docs pages and the CHANGELOG. A consumer gets these after the release and its lock
refresh. It then removes its own `validate_grants` call (harmless if kept) and its post-filter for
#312.
