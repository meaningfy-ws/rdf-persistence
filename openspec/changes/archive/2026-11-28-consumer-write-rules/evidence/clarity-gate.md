# Clarity gate: consumer-write-rules PLAN

run 1, 2026-11-27, 8.7/10, fail (fresh reviewer; actionability 9, specificity 8.5, consistency 9,
structure 9.5, disambiguation 7.5, reference clarity 9)

- PD-6: `toolkit_error` logs "internal error answered" with a traceback for every kind whose status
  is 500, before any branch (problems.py:259); with `RuleRefusal` mapped to `INTERNAL_ERROR`, a
  valid refusal is logged as an internal error unless the refusal branch is the first statement.
  Say "first statement of `toolkit_error`, before the 500 log".
- Stage 1 cannot use the worked example's `held_isbn` (it calls `reader.find`, stage 2), yet TC-5
  and TC-7 need a toy rule that refuses. Name the stage-1 toy rule in PD-9/task 1.3 (for example a
  fixed-value refusal with a fixed `holder`), and say 2.4 swaps in `held_isbn`.
- PD-8: route responses are built per route by `route_options` at registration
  (openapi.py:280-284); `install_openapi` only adds components. State how the generic create and
  replace operations are found in the document (thread `refusal_problems` into
  `AggregateOpenApi.create/replace`, or a named path/method rule in a post-pass).
- PD-11: the "sound cast" holds for `new` only. `old` is decoded from the stored types
  (`write_guards._decoded_stored`), so a replace that moves a root down its chain (stored `Book`,
  new subclass) gives a rule registered on the subclass an `old` that is a `Book`. Add the row, and
  either decode `old` as `name` or type `old` as the registered class's base.
- PD-10: `find` reads the store as committed but filters only removals. A unit of work that
  replaces B1's isbn v->w and then adds B2 with v finds B1 (stale) and refuses a write the commit
  would accept. Add the error-matrix row (accepted false refusal, or drop IRIs whose collected
  triples no longer match).
- Worked example / feature: `held_isbn` with `new.isbn is None` calls `find(Book, isbn=None)`,
  which asks for every book with no isbn, and refuses every isbn-less book. Guard `None` in the
  example and say it in the how-to (PD-15).
- PD-2: no guard against a consumer `Problem` subclass slot whose alias is a `Problem` field
  (`type`, `title`, `status`, `detail`, `instance`) with another range; it breaks assignability
  (PD-4) and the 409/422 check (PD-6). Refuse it at generation, with a TC.
- PD-1/TC-1: `rp_api_entrypoints` imports `../persistence/...` relatively; a consumer importing a
  technical module both by the new key and through a relative import loads one schema under two
  import names in `schema_map`. Add a TC loading a consumer schema that does both and asserting no
  duplicate module or class in the generated outputs.
- PD-14: `Seeded` "names the toy aggregates", but `reader_conformance` ships in
  `rdf_persistence.testkit` and must stay generic (AGENTS principle 3, `store_conformance` uses
  `EX` IRIs). Define `Seeded`'s fields (class, readable model, unreadable model, other-class model,
  slot and value for `find`) with no toy class in the package.
- PD-13/PD-14: the fake diverges from `Session.find` where the kit does not look: a non-root class
  (real `ValueError`, fake `[]`), a value of the wrong type (real `BadQuery`, fake `[]`), an IRI vs
  literal slot, a multivalued slot, a subclass instance. Add kit cases or state the divergence in
  the fake's docstring.
- Worked examples: one; MEDIUM needs two (add the in-process unit-of-work refusal or the
  unregistered-class 500).
- Task 2.1: the existing reader stub in `tests/unit/collaboration/test_aggregate_validators.py`
  (and `tests/generator/unit/test_lock.py`) must gain `find` or `make typecheck` fails; name it.

run 2, 2026-11-27, 9.0/10, pass (fresh reviewer; actionability 9, specificity 9, consistency 8.5,
structure 9.5, disambiguation 9, reference clarity 8.5)

- PD-6 refusal before the 500 log: closed (`kind_of` and its assert stay first, harmless; the
  branch precedes the log at problems.py:259).
- Stage-1 toy rule: closed (PD-9a `fixed_refusal`, no reader call; `held_isbn` comes in 2.1/2.4).
- PD-8 where `anyOf` is written: closed (verified `route_options`, `AggregateOpenApi.create` and
  `replace`, router.py:461, the `openapi()` closure of `install_openapi`).
- PD-11 `old` unsound: closed (`old: BaseModel | None`, matches `_decoded_stored`; TC-10 pins it).
- PD-10 stale `find`: closed (leaves out `context.collected`, fails safe on `KeyConflict`, worked
  example 2; consistent with DEC-5, the spec delta, the no-go and the kit, which has no
  transaction).
- `None` in `held_isbn`: closed (`find` raises `TypeError`; the example guards it).
- PD-2 shadowed `Problem` field: closed (PD-2a, TC-3b).
- One schema under two import names: closed (PD-1a, TC-1b).
- Generic `Seeded`: closed (PD-14 fields, no toy class in the package).
- Fake vs real divergences: closed (PD-13 contract, PD-14 cases).
- Two worked examples: closed.
- Task 2.1 reader stubs: closed for `test_aggregate_validators.py` (`NoReader`), but
  `tests/generator/unit/test_lock.py` holds no reader stub (its `classes_of` is a lock helper):
  drop it from 2.1; the ast-grep sweep stays.
- NEW contradiction: the error-matrix row "The fake asked a `Contains`, `None` or dotted `find` |
  `NotImplementedError`" contradicts PD-13 and TC-13 (`None` raises `TypeError` in both readers).
  Fix: remove `None` from that row.
- Minor: DEC-6 "a rule receives that class" reads as both arguments; say "as its new value", as
  PD-11 and the spec delta do (#387's acceptance is met by `new`). Stage 1 still ships alone.
