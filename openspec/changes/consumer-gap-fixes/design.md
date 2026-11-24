# Design: consumer-gap-fixes

> Derives from: EPIC `consumer-gap-fixes` (`proposal.md`: #304, #306, #311, #312). Its DEC-1 to DEC-7
> are cited here, not restated. The delivery decisions below are D-n.

## Context

Four defects reported by the first consumer, each in one place. The code facts the plan rests on
were read on `develop` at `8a3af499` and checked by the gate's attack (run 1):

- `uml/slots.py`: a multiplicity's flags come from `_flag`, which gives `True` or **`None`**,
  never `False` (`_flag`, l.63; used for `required` and `multivalued`, l.91-92). `usage_of` builds a
  class's `slot_usage` from `_shape_kwargs(shape, differing)`, which skips `None` and `False`. So
  a `1` that differs from a parent's `0..*` writes no `multivalued`, and the class inherits the
  parent usage's `true`. `share` calls `usage_of` for **every** usage of a slot whose limits
  differ (l.464-467). LinkML's `induced_slot` lets the most specific usage win, and an explicit
  `False` is not empty, so `B`'s `false` overrides `A`'s `true` (checked on linkml-runtime 1.12.1).
- `Tenancy.set_grants` (`tenancy.py` l.810) runs only `self._grant_validators`. The route
  (`router.py` l.323) calls `self._kit.rules.validate_grants(grants, access.tenant)` first.
  `problems.py` l.102-103 maps `UnknownRole` and `InvalidGrant` to the 400 `invalid-body` problem.
  `Tenancy` is a public export and is built in `kit.py` (l.212) and directly in about 25 test call
  sites (`tests/unit/tenancy/tenancy_helpers.py`, `tests/integration/tenancy/conftest.py`, …).
  `AccessRules` defaults to `DEFAULT_IRIS`, and `with_iris` rebinds it (`access.py` l.193).
- `rdf_persistence/__init__.py` exports lazily through `_LAZY_MODULES` and `__getattr__`.
  `state_iri` lives in `collaboration/services/workflows.py` l.77.
- `Session.find` → `_filters` → `_filter` → `Filter(slot, value=_text(item))`, and `_text(None)`
  is `"None"`. `Listings._filtered` resolves a `Filter` into a `Condition`. Equality calls
  `typed_value`, which refuses `""` for a non-string range. `condition_patterns` (`listing.py`
  l.217) puts every non-contains condition through `condition_pairs` as a `?root <p> <value>`
  pattern. It serves the listing's page and count queries (l.66-71, l.336) and `Session.matches`.
  The key guard's conditions come from `rule_filters` (`reference_collections.py` l.115-121) and
  never carry absence. `contains_patterns` lives in `core/domain/sparql.py` (l.184-199).
- `listable_slots` (`listing.py` l.150-160) drops every slot whose name is in `RESERVED`, so a
  reserved name loses filtering, sorting and its OpenAPI parameters. The listing's OpenAPI
  parameters are built at runtime in `AggregateOpenApi._query_parameters` (`openapi.py`
  l.446-456), not generated.

## Goals / Non-Goals

**Goals:** the four issues' acceptance criteria, each as a test that fails first; one refusal for
grants; one renderer for absence.
**Non-Goals:** the EPIC's No-gos.

## Decisions

- **D-1 (DEC-6):** `Filter` and `Condition` both gain `filter_absent` (`ifabsent: "false"`), as they
  already share `filter_contains`. `filter_value` and `condition_value` stay required. An absence
  filter carries the value `""`, and nothing reads it. Rejected: making the value optional, which
  ripples into every reader of `Condition.value`.
- **D-2:** `condition_patterns` splits three ways: equal (neither contains nor absent), containing,
  and absent. The absent ones render through a new `absent_patterns(variable, predicates)` in
  `core/domain/sparql.py`, next to `contains_patterns`. It writes
  `FILTER NOT EXISTS { ?{variable} <p> ?{variable}_a{n} . }`, and its variable name is checked as
  `contains_patterns` checks one. `Listings._filtered` resolves an absence filter with `_slot`
  only, so an unknown slot gives the same `BadQuery` and `typed_value` is never called. A filter
  with both `contains` and `absent` is refused with `BadQuery`.
- **D-3:** `list_request` reads each `absent` value as `Filter(slot=<value>, value="", absent=True)`.
  `RESERVED` gains `ABSENT = "absent"`. A slot named `absent` therefore leaves `listable_slots`: no
  equality, contains or sort on it, and no OpenAPI parameter, the same as a slot named `sort` today
  (RISK-5).
- **D-4 (DEC-2):** `Tenancy.__init__` gains a required keyword `rules: AccessRules` and stores
  `rules.with_iris(self._iris)`, after `self._iris` is resolved (`iris or Iris(settings)`; a `None`
  `iris` would leave the rules without a policy), so a custom IRI policy's aggregate targets validate.
  - This is **BREAKING** for direct constructors (CHANGELOG). `kit.py` passes `self.rules`.
  - `set_grants` reads the record first, so a missing tenant stays `NotFound`. It then calls
    `self._rules.validate_grants(grants, tenant)`, then the grant validators, then writes.
  - The route's own call (l.323) is removed.
  - The test helpers are updated to pass rules whose role definitions hold the roles their tests
    grant (for example `librarian` in `test_validators_adversarial.py`).
- **D-5 (DEC-1):** in `usage_of`, a `required` or `multivalued` field in `differing` is written as
  `true` or `false`: a `None` (from `_flag`) is written as `false`. `_shape_kwargs` is unchanged
  for `slot_of`, where an agreed unset flag writes nothing. Every usage of a slot whose
  `required`/`multivalued` differs gains an explicit value, including classes unrelated to the
  narrowing (RISK-1). DEC-1 accepts that, rather than walking the ancestors.

## Algorithm / approach

### Stage 1, #304 (converter)

Test first in `tests/generator/unit/test_uml_rules.py`. Model the issue's reproduction: abstract
`A` with `p 0..*` to `V`; «root» `B is_a A` with `p 1` to `W is_a V`; `unique_key = k: p`.

- `B.slot_usage.p` is `{range: W, required: true, multivalued: false}`.
- `SchemaView.induced_slot("p", "B").multivalued` is false.
- The generator's checks accept `k`.

A second case (E2): `A p 1..1`, `B p 0..1` writes `required: false`. A third (E3): usages that
agree write nothing.

Worked example. Before: `B: slot_usage: {p: {range: W, required: true}}`, and the induced slot is
multivalued. After: `B: slot_usage: {p: {range: W, required: true, multivalued: false}}`.
`A`'s own usage keeps `multivalued: true`.

### Stage 2, #306 (grants)

Test first, in `tests/unit/tenancy/` (a new `test_set_grants_roles.py`, built with
`tenancy_helpers.py`), and one route test in `tests/unit/api/test_router.py`:

- `set_grants` with an undefined role (E4), then with a system-only role (E5), raises
  `UnknownRole`, and the record's version is unchanged.
- A refusing grant validator is not called.
- A missing tenant with a bad role gives `NotFound` (E15).
- The route returns the same 400 problem.

### Stage 3, #311 (export)

Test first in `tests/unit/package/test_lazy_exports.py`. `from rdf_persistence import state_iri`
works, `"state_iri" in rdf_persistence.__all__`, and the object is the one in
`collaboration.services.workflows`. Then the lazy entry, `make refresh-surface`, and the how-to import.

### Stage 4, #312 (absence)

1. `rp_persistence_services.yaml`: a `filter_absent` slot (`slot_uri: rp:filterAbsent`,
   `alias: absent`, boolean) on `Filter` and `Condition`. Then `make generate`.
2. Tests first.
   - Unit, `tests/unit/core/` beside the `contains_patterns` tests: `absent_patterns` output, and
     `condition_patterns` with no absent condition rendering exactly as before (E14).
   - Unit, `tests/unit/api/test_listing_routes.py`: `list_request` with `absent`, E11, E13, E16, E17.
   - Integration on the toy: `tests/integration/store/test_session.py` (`find`: E9, E10, E18) and
     `tests/integration/api/test_listing.py` (`GET …?absent=`, with `total`, a multivalued slot, E12).
3. `session._filter`: `None` gives `Filter(slot, value="", absent=True)`, and `_items` refuses
   `None` inside a list (DEC-4).
4. `Listings._filtered`, `condition_patterns` and `absent_patterns`, as in D-2. The count query
   follows, because it calls `condition_patterns`.
5. `openapi.py` `_query_parameters`: an `absent` parameter, an array whose enum is the listable slot
   names. Then `reference/http-api.adoc` (absence, the reserved names, E18).

Idempotency: every stage is a read or an if-version-guarded write, unchanged in kind. A retried
`set_grants` is refused or applied exactly as the first try was.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Patch converted YAML or generated code for #304 | Fix `usage_of`; regenerate | LinkML is the single source |
| Validate roles in both `set_grants` and the route | One call, in `set_grants` | Two paths drift (the bug itself) |
| Build `AccessRules` inside `Tenancy` | Receive it; rebind with `with_iris` | The kit owns the role definitions |
| Render absence in the listing only, or with `?_absent_n` | `absent_patterns` through `condition_patterns` | One renderer; the variable naming of `sparql.py` |
| Treat `?slot=` (empty) as absence | `absent=<slot>` | An empty string can be a value (DEC-5) |
| Post-filter `find` results in Python | Filter in SPARQL | Paging and `total` would be wrong |

## Error matrix

| # | Input | Detection | Response | Fallback |
|---|---|---|---|---|
| E1 | `B` narrows an inherited `0..*` to `1`, with a key on it | `usage_of` writes `multivalued: false` | key accepted | n/a |
| E2 | `B` narrows `1..1` to `0..1` | `usage_of` writes `required: false` | `B.p` optional | n/a |
| E3 | every usage single-valued | `slot_of` (unchanged) | nothing written | n/a |
| E4 | `set_grants`, undefined role | `validate_grants` in `set_grants` | `UnknownRole`, nothing stored; 422 `invalid-body` on HTTP (D-6) | name a defined role |
| E5 | `set_grants`, system-only role | as E4 | `UnknownRole` | as E4 |
| E6 | `set_grants`, foreign target or non-IRI assignee | `validate_grants` | `InvalidGrant`, nothing stored | fix the grant |
| E7 | stored grants name an undefined role; the new set drops it | `validate_grants` reads the new set only | stored: the clean-up path (RISK-2) | n/a |
| E8 | as E7, the new set keeps it | as E4 | `UnknownRole` naming the role | drop that grant (how-to) |
| E15 | missing tenant and a bad role | `self.get` before validation | `NotFound` | n/a |
| E19 | `Tenancy` built with a custom IRI policy; grant on an aggregate graph | `rules.with_iris(iris)` | accepted | n/a |
| E9 | `find(cls, s=None)` | `_filter` | the absent ones matched | n/a |
| E10 | `find(cls, s=[None, "x"])` or `s=[None]` | `_items` | `ValueError` "None cannot be combined with values for s" | two calls |
| E18 | `find(cls, s=None)` where `s` has `ifabsent` | none: the mapper always writes the default | matches nothing; documented | filter on the default value |
| E11 | `?absent=nosuch` | `Listings._slot` | `BadQuery` 400 "has no slot 'nosuch'" | fix the name |
| E12 | `?absent=s&s=x` | none | matches nothing (consistent; documented) | n/a |
| E13 | `?absent=` (empty) | `_slot("")` | `BadQuery` 400 | n/a |
| E16 | a model slot named `absent`; `?absent~=x` | `listable_slots` drops it | `BadQuery` 400 "has no slot 'absent'" | rename the slot (RISK-5) |
| E17 | a `Filter` with `contains` and `absent` (through the model) | `_filtered` | `BadQuery` | n/a |
| E14 | any condition set with no absence (listing, `matches`) | `condition_patterns` | renders exactly as before | n/a |

## Risks / Trade-offs

- **RISK-1 (#304 changes output).**
  - A consumer that narrows roles will hit it, and code that read a list breaks.
  - Every usage of a slot whose `required`/`multivalued` differs also gains an explicit `true` or
    `false`. That is noise, but harmless.
  - Mitigation: the CHANGELOG and the PR are marked **BREAKING** and name the shape. The toy's
    golden diff is reviewed: it may hold only explicit flags on slots whose usages differ.
- **RISK-2 (#306 meets stored bad grants).**
  - Possible, only for a tenant written through `set_grants` before the fix.
  - Mitigation: the refusal names the role (E8). The tenancy how-to gains a paragraph, "a refused
    set_grants": read the grants, drop the named one, write again (E7).
  - The `Tenancy` constructor change is **BREAKING** for a consumer that builds it directly; the
    kit path is unchanged.
- **RISK-3 (#312 changes what `None` means).** Unlikely to break anyone, since `None` matched
  nothing before, but the change is silent. Mitigation: a CHANGELOG "Changed" line.
- **RISK-4 (lock drift).** Certain without action. Mitigation: a release after stage 4 (DEC-7), and
  a comment on each issue naming the version.
- **RISK-5 (a slot named `absent`).** Unlikely. Such a slot loses all listing support (E16).
  Mitigation: a CHANGELOG line; the listing docs list the reserved names.

## Delivery decisions

- **D-6 (stage 2, #306):** the refusal on `PUT …/grants` is **422** `invalid-body`, not 400 as
  E4 and the `rp-tenancy` delta said: `problems.py` maps `UnknownRole`/`InvalidGrant` to 422, and
  the existing route tests assert it. Nothing changed in behaviour; E4 and the delta now say 422.
- **D-7 (stage 2, #306):** no tenancy how-to page exists, so RISK-2's "a refused set_grants"
  paragraph is in `user-manual/access.adoc` ("Grant and prohibit"), next to the grants it explains.
- **D-8 (stage 2, #306):** a test that swaps `kit.rules` after the kit is built now swaps the
  tenancy's too, through `tests/scene.py` `use_roles`, because the tenancy takes its rules at
  construction (D-4). The helper sets the tenancy's private `_rules`; no public setter is added,
  since only tests change roles after start-up.

## Open Questions

None. DEC-5's syntax is the owner's to review in PR 4.
