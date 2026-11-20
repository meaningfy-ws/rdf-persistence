<!-- PLAN (design half) of unique-key-nulls-equal. PLAN = this file + tasks.md. -->

# Design: unique-key-nulls-equal

> Derives from: EPIC `unique-key-nulls-equal` (`proposal.md`, issue #202), DEC-1 to DEC-3.
> Builds on the archived `2026-11-14-cross-aggregate-unique-keys` (its PD-5 to PD-16).

## Context

How a key across aggregates works today (`rdf_persistence/persistence/services/unique_keys.py`):

- There is **no stored claim**. A claim (`KeyClaim`: key, root, values) is computed in memory from
  the triples of the change (`claims_of`), and the guard is a `FILTER NOT EXISTS` over the
  *aggregate graphs* of the other roots of the tenant (`KEY_HELD`, joined to the registry), in the
  same update request as the write. The stored graph is the claim.
- `_values_of` returns no values, so no claim, when a key predicate has no value; a blank-node
  object counts as no value (`claims_of`); two values or more raise `InvalidBody`.
- `same_value` refuses two equal claims of one transaction; `diagnosis` re-reads with the same
  patterns after a refused guard; `duplicates_query` groups the stored values
  (`value_patterns`, `GROUP BY ?v0 … HAVING COUNT(DISTINCT ?key_root) > 1`).
- `AggregateKey` (`rp_core.yaml`) has `key_name`, `root_class`, `key_predicates`;
  `aggregate_keys()` (`schema_structure.py`) builds them from the scoped `unique_keys`.
- The hard check (`checks/hard.py` `_scoped_key_reasons`) refuses `consider_nulls_inequal: false`
  on every scoped key. The only allowed `rp_unique_scope` value is `tenant` (`UniqueScope`), and
  any other value is already refused as `rp_unique_scope: 'x' is not one of ('tenant',)`.
- **Multi-valued slots (the EPIC's rabbit-hole), confirmed:** the hard check refuses a multivalued
  slot in a scoped key (`_bad_key_slot`), and a raw session call with two values for a key
  predicate raises `InvalidBody`. Both rules stay; the option changes only the zero-value case.

## Goals / Non-Goals

**Goals**
- G-1: a scoped key with `consider_nulls_inequal: false` passes `rp-generate` (DEC-1, DEC-2).
- G-2: for such a key, an absent slot is one value, guarded in the same update (spec scenarios 1, 2).
- G-3: `key_duplicates()` reports stored duplicates that share an absence.
- G-4: keys without the option behave as today, byte for byte in the queries they send.

**Non-Goals**
- In-aggregate (unscoped) keys and their generated validators (PD-10).
- Any new scope, partial or conditional key; cleanup of existing duplicates (EPIC no-gos).

## Decisions

- **PD-1** (DEC-1): `AggregateKey` gets `key_counts_absent: boolean`, `ifabsent: false`, a global
  slot of `rp_core.yaml` named like PD-16's `key_*` slots. `aggregate_keys()` sets it `True` exactly
  when the declaration's `consider_nulls_inequal is False` (`None` and `True` give `False`). A
  hand-built `AggregateKey` without it keeps today's behaviour.
- **PD-2** (DEC-3): the marker is `ABSENT_KEY_VALUE`, the IRI `rp:absentKeyValue`
  (`https://meaningfy.ws/ns/rdf-persistence#absentKeyValue`), defined in
  `schema/services/vocabulary.py` beside `PENDING_SINCE` and built the same way (plumbing, not a
  slot, so no model). It lives **only in memory and in the report**: in `KeyClaim.values` and in
  `KeyDuplicate.key_values` (as its IRI text). It is never written to a graph and never appears as a
  value in a guard pattern.
- **PD-3** (DEC-3): absence is matched by structure, not by the marker. In a guard or diagnosis, a
  position holding the marker renders as
  `FILTER NOT EXISTS { ?key_root <p> ?key_absent_n . FILTER (!isBlank(?key_absent_n)) }` inside the
  `GRAPH ?key_graph { … }` of `KEY_HELD`, after the present-value and type patterns (value first,
  as PD-7 of the archived change). A blank node is no value on both sides (claims already drop it).
- **PD-4** (DEC-3): `_values_of` (called by `claims_of`, so before anything is sent) raises
  `InvalidBody` when a value of a `key_counts_absent` key
  equals `ABSENT_KEY_VALUE`. This is what makes "never a value an application can store" true for
  the claim: without it, a root holding the marker IRI would equal an absent claim in `same_value`.
- **PD-4a**: so that the sketch below and PD-4 agree, the check sits in `_values_of`, the one
  function that reads the values per predicate; `claims_of` only collects its result.
- **PD-5**: `duplicates_query` for a `key_counts_absent` key renders, per predicate,
  `OPTIONAL { ?key_root <p> ?key_raw_n . FILTER (!isBlank(?key_raw_n)) }
  BIND (COALESCE(?key_raw_n, <marker>) AS ?v_n)`; keys without the flag keep `value_patterns`
  unchanged (G-4). `duplicates()` needs no change: `str(row[n])` gives the marker's IRI text.
- **PD-6**: two pure renderers join `domain/sparql.py` (PD-12 of the archived change):
  `absent_patterns(subject, predicates)` and `optional_value_patterns(subject, predicates, default)`,
  validating the variable name like `match_patterns` and rendering terms through `term()`.
- **PD-7** (DEC-2): `_scoped_key_reasons` drops the blanket reason. When the option is set and the
  scope value is not allowed, it adds `consider_nulls_inequal: false needs rp_unique_scope: tenant`
  (beside the existing scope-value reason). An unscoped key on a root is already refused with the
  fix `rp_unique_scope: tenant`.
- **PD-8**: test data. Session tests build the key by hand over the toy `Book`:
  `AggregateKey(key_name="title_subtitle", root_class=bibo:Book, key_predicates=[dcterms:title,
  dcterms:alternative], key_counts_absent=True)`; the toy schema is not changed, so no existing test
  meets the new key. `dcterms:alternative` needs no slot: claims read triples, not models. It
  plays the spec scenarios' "subtitle".
- **PD-9** (owner, 2026-11-20, Q-1): the spec deltas are MODIFIED requirements of the living specs.
  `rp-aggregate-store` "Unique keys hold across the aggregates of a tenant" keeps "an absent slot
  claims nothing" for keys without the option and adds the counted absence; "Existing key
  duplicates can be reported" adds the shared absence. `rp-generation` "A unique key across
  aggregates is declared with its scope" accepts the option at tenant scope and carries the
  unsupported-scope scenario.
- **PD-10** (owner, 2026-11-20, Q-2): in-aggregate (unscoped) keys are out of scope. Their
  generated validators and shapes already treat two absent values as equal for every key
  (`architecture/generation.adoc` section `[#extensions]`, the `pydantic_validators.py` row: "an
  absent value counts, and two absent values are equal"; the `shacl_constraints.py` row likewise), so the option changes nothing for them; no check is added.
- **PD-11** (owner, 2026-11-20, Q-3): with every slot of the key absent, at most one root per type
  and tenant may lack all key values, as SQL `NULLS NOT DISTINCT` does; documented in the how-to.

## Algorithm / approach

```python
# unique_keys.py
def _values_of(own, key, iri) -> tuple[Value, ...]:
    per_predicate = [...]                                   # as today; 2+ values -> InvalidBody
    if key.key_counts_absent:                               # PD-1
        values = tuple(vs[0] if vs else ABSENT_KEY_VALUE for vs in per_predicate)
        if any(vs and vs[0] == ABSENT_KEY_VALUE for vs in per_predicate):
            raise InvalidBody(...)                          # PD-4
        return values
    return tuple(vs[0] for vs in per_predicate) if all(per_predicate) else ()   # unchanged

def _values(claim) -> SparqlTerm:                           # used by guard() and diagnosis()
    present = [(p, v) for p, v in pairs if v != ABSENT_KEY_VALUE]
    absent  = [p for p, v in pairs if v == ABSENT_KEY_VALUE]
    held = match_patterns("key_root", [*present, (RDF.type, root_class)])
    return join([held, absent_patterns("key_root", absent)]) if absent else held  # PD-3, G-4
```

Worked examples (key `[title, alternative]`, counts absent):

| Stored | Change | Claim | Result |
|---|---|---|---|
| A: Dune / — | add B: Dune / — | (Dune, ABSENT) | guard: A has title Dune, type Book, no alternative → `KeyConflict(iris=[B])` |
| A: Dune / — | add B: Dune / Messiah | (Dune, Messiah) | no holder → stored |
| A: Dune / — | add B: Dune / `""` | (Dune, `""`) | `""` is a present literal; A has no triple → stored |
| A: Dune / Messiah, B: Dune / — | replace A with Dune / — | (Dune, ABSENT) | B holds it → `KeyConflict(iris=[A])` |
| A: Dune / Messiah, B: Dune / — | one tx: A → Dune / —, B → Dune / Messiah | differ; A, B excluded | stored |
| A: Dune / — | replace A: Dune / Messiah, then Dune / — | each recomputed | both stored (own root excluded) |

**Present → absent → present:** nothing is released or re-taken by hand, because nothing is
stored but the graph: each replace computes its claim from its new triples, and the guard excludes
the roots the transaction replaces or removes. The old claim disappears with the old graph in the
same update request.

**Idempotency:** the guard writes nothing of its own; a retried commit is checked again against
the stored graphs, so a replay of an accepted commit fails on its version, not on its key, as today.
Concurrency is the store's: two updates are serialised and the second one's guard sees the first.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Write the marker into the aggregate graph | Match absence with `FILTER NOT EXISTS` (PD-3) | It would break shapes, reads and round trips, and stored data would need migrating |
| Use `""` or a literal as the marker | An IRI in the toolkit namespace, held only in memory (PD-2) | A literal is an application value; `""` is a real value distinct from absence |
| Match the marker IRI in SPARQL | Structural absence (PD-3) | No graph holds it, so the guard would never match |
| Forget `!isBlank` in the absent pattern | Treat a blank node as no value on both sides (PD-3) | A claim drops blank nodes; a stored blank node would otherwise hide an absence |
| Change `value_patterns` or the query of an unflagged key | Branch on `key_counts_absent` only (PD-5) | G-4 and the no-go "no change to keys without the option" |
| Put a value or the marker into a pattern with an f-string | `term()`, the PD-6 helpers | Injection (archived DEC-3) |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Add with an absence another root of the type shares | guard `ASK` fails; `diagnosis` finds the claim | `KeyConflict(iris=[root], keys=[name])`, nothing written; router 409 |
| Two concurrent adds of Dune / — | the store serialises; the second guard sees the first graph | exactly one stored, the other `KeyConflict` (IT-NE-1) |
| Two changes of one tx both Dune / — | `same_value` (marker equals marker) | `KeyConflict` naming both, nothing sent |
| Value `""` against an absence | term inequality / no triple | no clash |
| Blank-node value for a key slot (raw call), or stored | claim drops it; `!isBlank` in the pattern | counted as absent on both sides |
| A key slot whose value is the marker IRI | `_values_of`, via `claims_of` (PD-4, PD-4a) | `InvalidBody`, nothing sent |
| Two values for a key slot (raw call) | `_values_of` | `InvalidBody`, unchanged |
| Every slot of the key absent | claim (ABSENT, …, ABSENT) | at most one such root per type and tenant (PD-11); the guard scans the type (RISK-2) |
| Option turned on over stored duplicates sharing an absence | `key_duplicates()` | entries with `key_values` holding the marker's IRI text; a replace keeping the absence is refused until fixed (no cleanup, EPIC) |
| Stale replace that also clashes | version diagnosis first | plain `Conflict`, unchanged |
| Key without the option, slot absent | `key_counts_absent` false | no claim, as today (G-4) |
| Option with `rp_unique_scope: world` | hard check | refused, naming `rp_unique_scope: tenant` (PD-7) |
| Option on an unscoped in-aggregate key | not checked | unchanged: its validator already counts two absences as equal (PD-10) |
| Guard refused, holder removed before the diagnosis read | diagnosis finds nothing | `Conflict(iris=())`, retry passes, unchanged |

## Risks / Trade-offs

- **RISK-1** — rdflib (fake store) and Fuseki disagree on a nested `FILTER NOT EXISTS` inside
  `GRAPH ?g` or on `COALESCE` grouping (low; high: the unit tier would pass while Fuseki lets a
  duplicate in). Mitigation: IT-NE-1 and IT-NE-2 run the guard and the report on Fuseki.
- **RISK-2** — a claim with every slot absent has only the type pattern to anchor on, so the guard
  walks every root of the type (low likelihood: keys usually have a required slot; medium impact).
  Accepted for SMALL; recorded in the how-to. Revisit if a consumer keys only optional slots.
- **RISK-3** — `key_duplicates()` shows the marker as text, which looks like a literal of the same
  text (very low; low). Accepted; documented beside the existing "same text, other datatype" note.
- **RISK-4** — a schema already stored data with the marker IRI as a value (near zero: toolkit
  namespace). The report would group it with absences; PD-4 refuses new writes. Accepted.

## Open Questions

None. The owner settled three on 2026-11-20 (`inputs/qa.md`), recorded as PD-9 to PD-11.

## Delivery decisions

- **D-1** (lead, 2026-11-20, impact before 1.2 to 1.4): GitNexus rates `AggregateKey` CRITICAL
  (fan-in of the shared `RpModel` base, 134 implementations), `sparql.py` HIGH (fan-in of the
  existing helpers) and `_scoped_key_reasons` HIGH (3 dependents, all on the hard-check path).
  The changes are additive (a field defaulting to `false`, two new functions, a narrowed
  refusal), so no existing caller changes meaning. Proceed; G-4's query-text test and the full
  gates guard it.
- **D-2** (lead, 2026-11-20): 1.2, 1.3, 1.4 and 1.7 (docs only, no roadmap dependency) run as
  parallel builders in the one worktree, on disjoint files; a gate failure in another builder's file is T2, re-run by the lead. Gates in
  the sandbox run with `UV_CACHE_DIR=$TMPDIR/uv-cache` (the shared uv cache is read-only there).
- **D-3** (lead, 2026-11-20, from the 1.4 report): D-2 missed one coupling: the generated-code
  freshness plugin stops every pytest run while a model task (1.3) is between its schema edit and
  `make generate`, so 1.2 and 1.4 cannot see red or green until 1.3 regenerates. They resume
  after it. Generator code is a freshness input too (1.2's `hard.py` blocked 1.4 the same way),
  so from here builders run one after another, each ending with `make generate` when it touched
  an input. Next time, model and generator tasks run first or in their own worktrees. Also,
  `term()` refuses an IRI containing `>` (`SparqlError`), it does not escape it (task 1.4's
  wording); the tests assert the refusal, which is the existing, safer behaviour.
- **D-4** (lead, 2026-11-20, from the 1.2–1.4 verification): PD-1 is the first model change
  since the per-theme move, and `tests/unit/test_combined_artefacts.py` (domain-model-per-theme
  TC-03) pins `core`'s `shapes.ttl` and `context.jsonld` byte for byte to the v0.6.0 copies, so
  any model change fails it. That guard proved a refactor changed no output; the refactor shipped
  in v0.7.0. Re-baselining would leave non-0.6.0 files in `tests/fixtures/v0_6_0/`. Decided:
  exclude those two files from the byte comparison only; their presence in `core`, the frames'
  and the lock's byte identity and the frame set stay guarded, and `make check-generated` keeps
  them fresh. The model change's own reference files (`tests/fixtures/model-shape.yaml`, the
  served TypeScript golden) were refreshed with their make targets. Developer may overrule.
- **D-5** (lead, 2026-11-20, from the 1.5 report): PD-5's `duplicates_query` rendered the
  `OPTIONAL` value patterns before the type pattern. An `OPTIONAL` evaluated with `?key_root`
  unbound binds it to any subject of the graph holding the predicate (a part, for instance); the
  type pattern then drops that row and the root lacking the value is never reported. Decided:
  for a `key_counts_absent` key the type pattern binds `?key_root` first, then the optional value
  patterns follow. Unflagged keys keep today's text (G-4). Guarded by a fake-store test whose
  aggregate graph has a part holding a key predicate, and by IT-NE-2 on Fuseki.
