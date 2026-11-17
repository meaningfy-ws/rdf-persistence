# Facts for the test-debt-paydown PLAN

Worktree `temp/wt/lead` at be129a0 (develop). Read-only; probes and outputs in `temp/paydown/`
(`profile_toy*.py/.out`, `probe_parts.py`, `cross_imports.py/.out`).

Two findings change the EPIC's wording:
- **No relay fake and no recording message bus are needed** (item 1): the relay is built inside
  `ServiceKit`, so a fake cannot be injected without a new constructor parameter; a public
  `Relay.paused()` is smaller. `RecordingObserver` + `bootstrap()` already is the recording bus.
  The `rp-testkit` capability line in proposal.md should change accordingly.
- **`poll_seconds` does not speed the in-memory run** (item 7): the in-memory bus delivers inside
  `publish`, and `wait_until_async` probes before it sleeps, so the in-memory cases never sleep.
  The saving is on the Redis lane.

---

## 1. Rule-5 monkeypatches

| Test | Current (file:line) | Seam already there? | Smallest change | Risk | Decision |
|---|---|---|---|---|---|
| `test_receive.py` KeyError | `tests/unit/entrypoints/test_receive.py:277-288`: `monkeypatch.setattr(Session, "is_recorded", broken)` raising `KeyError` | `FakeStore.on()` (`testkit/fakes.py:66`) is typed `PersistenceError` and counts calls per operation; the probe is one of several `query` calls of the session open | none fits: a fake can only produce what a port's contract allows; D-8 is about a *defect* (`KeyError` from toolkit code) | — | **Keep**, recorded as a rule-5 exception in `testing.adoc` ("a defect inside toolkit code that no port can produce") |
| `test_receive.py` LookupError | `:291-305`: `monkeypatch.setattr(world.cat.kit, "application_session", no_application)` | a schema with no application class would be the honest seam; the only toy schema (`tests/fixtures/library/library.yaml`) has one, and a second schema needs a generated package | — | high (new LinkML fixture + generation) | **Keep**, same recorded exception ("a configuration the toy schema cannot have") |
| `test_events_route.py` x2 | `:403-427` (TC-37a) and `:472-491` (TC-38): `monkeypatch.setattr(kit.relay, "run_once", not_now)` "the commits stay pending" | `Relay` (`services/relay.py:76`) has `_lock` (every round is `async with self._lock`, `:121-125`); the relay task is started by the lifespan (`entrypoints/service.py:176`) on the kit's own `Relay` (`kit.py:198`), so a fake cannot be swapped in after start | add `Relay.paused()` (async context manager holding `_lock`: no round runs while held; one runs after if woken). Tests: `async with kit.relay.paused(): ...` | low: public, additive; a test that forgets to leave the block hangs (pytest-timeout ends it) | **Add `Relay.paused()`** with its own unit test in `test_relay.py`; no relay fake |
| `test_service_kit.py` spy | `tests/unit/entrypoints/test_service_kit.py:658-675` (TC-82): `monkeypatch.setattr(MessageBus, "publish", spy)` with `kit.bus is None` | the hook is `kit._publish` (`kit.py:208-213`): `if self.bus is not None: await self.bus.publish(...)`. With no bus there is no `MessageBus` instance to record; removing the guard makes `None.publish` raise, the PUT fail, and `replace_the_book` fail | drop the spy; keep `assert kit.bus is None`, the write's success and "the commit is recorded" | none: the mutant the spy guards is already killed by the request failing | **Drop the spy**; no recording bus (`RecordingObserver` + `bootstrap` already record, `testkit/messages.py:11`) |
| `test_migrate_dataset.py` NOTHING | `tests/unit/services/test_migrate_dataset.py:219-228`: `monkeypatch.setattr(migration_runner, "migration_request", lambda *_: NOTHING)` | the same file already doubles rdflib with `class Failing(Dataset)` (`:241-249`) | `class Inert(Dataset)` whose `update` does nothing: the stamp stays, "went backwards" | low | **Dataset subclass** (third-party double, not toolkit code) |
| `test_migrate_dataset.py` DROP_STAMPS | `:231-238` | as above | `class Unstamping(Dataset)` whose `update` removes the stamps graph | low | **Dataset subclass** |
| `test_migrate_dataset.py` SparqlError | `:263-272`: our own template raising `SparqlError` must escape (not become `InvalidBody`); the call is outside the `try` (`services/migration_runner.py:130`) | `migration_request` raises `SparqlError` when "the schema id is not an IRI that SPARQL can carry" (`services/migrations.py:227-237`) | build a chain whose `Migration.schema_id` cannot be a SPARQL IRI (e.g. contains a space or `>`), if `Migration` validation lets it through | medium: the model may refuse the id first | **Real data** if the model admits it; else keep the patch as a recorded exception (check first in the task) |
| `test_migrate_dataset_adversarial.py` | `:188-201`: `patch.setattr(Dataset, "contexts", counted)` counts full graph walks (PD-26) | the dataset is passed in; `many_graphs()` builds it | `class CountingDataset(Dataset)` overriding `contexts`, built by `many_graphs`; also assert `small > 0` (today 0 == 0 would pass) | low-medium: if rdflib's SPARQL engine walks through another object than the passed dataset the count is 0 — the new `small > 0` assert catches that | **Dataset subclass** + non-vacuity assert |
| `test_generation_inputs.py` x2 | `tests/unit/generation/test_generation_inputs.py:193-221`: `monkeypatch.setattr(steps, "STEPS", ...)` | `generate(targets, base, steps, *, check)` (`generation/pipeline.py:217`) takes the steps; `main` only adds printing (`generation/cli.py:65-90`) | call `generate(read_targets(...), base, (render_step(...),), check=False)`: assert the returned problem names the fault / the bug escapes | low (the stderr printing is covered by other CLI tests) | **Call `generate` with injected steps** |
| `test_freshness.py` linkml version | `tests/unit/generation/test_freshness.py:139-145`: `linkml_version` → "0.0.1" | the manifest records `linkml` (`generation/manifest.py:99, 172-175`); `read_manifest` exists in the test file | rewrite the generated manifest's `linkml` field to `0.0.1` (through `GenerationManifest`, not a dict) | low | **Change the data, not the code** |
| `test_freshness.py` no extra | `:148-163`: `sys.modules` surgery + `linkml_version` → None | it simulates an absent optional dependency; the environment is the seam | — | — | **Keep** (recorded exception: "an absent extra") |
| `test_freshness.py` sha256 | `:338-351`: `sha256_of` → zeros for `rp_service.yaml` | `toy_copy` is a copy | append a comment line to the copied `rp_service.yaml` | low | **Change the data** |

Not in the Debt list: `test_service_kit.py:423` sets the public attribute `service.kit.max_restore_bytes`
(configuration, not code): leave it.

## 2. Rule-12 waits with no injectable clock

| Wait | Current | What exists | Smallest change | Risk | Decision |
|---|---|---|---|---|---|
| absence: default route | `test_events_route.py:258-264` `bob.take(1, timeout=0.2)` raises `TimeoutError` | no clock involved: it waits for nothing to come | **sentinel event**: commit a replace, `take(1)` is that `Replace` (nothing came before it) | none | no production change |
| absence: resume hides a2 | `:441-442` `carol.take(1, timeout=0.2)` | same | after `a3`, replace another book carol may read; the next event is that one | none | no production change |
| absence: other tenant | `:521-523` `ada.take(1, timeout=0.3)` | same | create a book in ada's tenant, replace it after the first tenant's replace; the next event is ada's | none | no production change |
| keep-alive after grant removal | `:293-301`, keep-alive 0.05 s via `mount(..., keep_alive=KEEP_ALIVE)` (`:28, :152-165`) | `add_events_route(keep_alive=...)` (`entrypoints/sse.py:54-63`) already injectable; the timer is `asyncio.wait_for(queue.get(), keep_alive)` (`services/event_stream.py:119`) | mount a second route with `keep_alive=0` for this test only. Probed (Py 3.13): `wait_for(q.get(), 0)` times out at once *even with an item ready*, so 0 means "keep-alive on every idle turn"; fine for a test that expects no event | low-medium: the stream spins (access re-read each turn, `access_ttl=0`) until the grant goes; only this test uses it | **keep_alive=0 on a dedicated mount**; no production change |
| relay d18 hanging publish | `tests/unit/services/test_relay.py:282-305`, `publish_timeout=0.05` | `Relay(publish_timeout=...)` already injectable (`relay.py:91, 197`) | `publish_timeout=0`, and `HangingBus`'s other-tenant branch must not suspend (record to the broker without awaiting a delivery). Probed: `asyncio.timeout(0)` cancels at the first suspension, so the hang times out at once and a non-suspending publish completes | low-medium: depends on the fake's other branch never awaiting; add a comment | **publish_timeout=0 + non-suspending fake branch**; no production change |

So stage 2 needs **no clock or interval parameter**: every one is already there or not needed.
The testkit's `probe_timeout` 0.01 s stays the one accepted exception.

## 3. Redundant production branches

- **Fuseki** (`rdf_persistence/adapters/fuseki.py:46-59`):
  ```
  if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
      raise StoreUnavailable(f"Fuseki answered {status}")
  ...
  if not response.is_success:  # 401, 403, 415, a redirect...
      raise StoreUnavailable(f"Fuseki answered {status}")
  ```
  Same class, same message; no 5xx is 404/405/409/400. No doc, spec or test names the text
  (`grep "Fuseki answered"` over docs/, openspec/specs/, tests/: none).
  **Decision: remove the `>= 500` branch** (and update the final comment to say "a server error,"). Risk none;
  `test_data_plane_statuses_map_to_errors` still covers 500/503.
- **auth** (`rdf_persistence/entrypoints/auth.py:38-41`):
  ```
  scheme, _, token = (authorization or "").partition(" ")
  if scheme.lower() != BEARER_SCHEME or not token.strip():
      raise InvalidToken("a bearer token is required")
  return await self._kit.verifier.verify(token.strip())
  ```
  The two halves are not alike:
  - *scheme* is a security guard, not redundant: without it a **valid** JWT sent as
    `Basic <jwt>` or `Token <jwt>` is accepted. The mutant survives only because the test's
    non-Bearer case (`"Basic YWRhOnB3"`, `test_service_kit.py:76-89`) carries no valid token.
    **Decision: keep; add one case: a valid token under another scheme is a 401.**
  - *empty token* is redundant by contract: `TokenVerifier.verify` must raise `InvalidToken` for a
    missing token (`services/tokens.py:25-31`), `JwksTokenVerifier` does (`adapters/jwks.py:85-86`),
    and the conformance matrix has `"empty"`. **Decision: remove `or not token.strip()`**; the
    `"Bearer"` (no-token) case keeps its 401 through the verifier.
  - Messages: the 401 problem carries type `invalid-token`; no spec or doc quotes "a bearer token is
    required" (`openspec/specs/rp-identity/spec.md:8` speaks of a bearer token only; api.adoc:323
    "Verify the bearer token."). No contract on the text.

## 4. P-20's remaining rows

Note: the file is now `tests/unit/adapters/test_token_verifier.py` (the Debt says `services/`).

**`test_an_invalid_token_is_refused`** (`:200-205`, list `INVALID_TOKENS` `:107-136`, builders
`:155-197`): 28 cases. The audit's "4 groups" are not spelled out anywhere; grouped here by the
refusal branch in `adapters/jwks.py:84-136` (and the generated `JwtClaims`, strict fields + `sub` pattern):

| Branch | Cases | Keep | Drop |
|---|---|---|---|
| missing (`jwks.py:85`) | empty | empty | — |
| malformed header (`:97-99`) | garbage | garbage | — |
| algorithm (`:101`) | alg-none, alg-none-with-a-known-kid, hs256-with-the-public-key | alg-none | the other two: each has its own test with `match="is not accepted"` (`:214-226`) |
| no kid / unknown kid (`:103`, `:153`) | missing-kid, unknown-kid | both (two branches) | — |
| PyJWT refusal (`:110-123`) | wrong-issuer, wrong-audience, bad-signature, no-exp, no-sub | the spec's three (signature, issuer, audience) + no-sub | no-exp (also refused by the model's required `exp`; same branch as no-sub) |
| claims model (`:124-127`) | exp-as-a-numeric-string, exp-as-a-bool, nbf-as-a-numeric-string, sub-as-a-number, exp-not-a-number, empty-sub, whitespace-sub, padded-sub | exp-as-a-bool (bool is an int: the strict case), nbf-as-a-numeric-string (nbf's strictness), sub-as-a-number, padded-sub (the `sub` pattern) | exp-as-a-numeric-string, exp-not-a-number, empty-sub, whitespace-sub |
| non-finite (`:128-129`) | exp-nan, exp-infinite, nbf-nan, nbf-negative-infinite | exp-infinite (kills `isfinite`→`isnan`), nbf-nan (the `nbf or 0.0` half) | exp-nan, nbf-negative-infinite |
| expired (`:132`) | expired, expired-a-minute-ago, expires-this-instant | expires-this-instant (boundary `<=`) | expired, expired-a-minute-ago (`test_an_expired_token`, `:207`, keeps the message) |
| not yet valid (`:134`) | not-yet-valid | it | — |

28 → 17 cases (11 dropped; the audit estimated ~9). Gap seen while grouping: `UNUSABLE_SUBJECTS`
(`jwks.py:37`, `"."` and `".."`) has no case in the matrix; add `sub-dot` while here (it is the only
case for `jwks.py:130`). Each drop confirmed by D-3 (hand-mutate the branch, the kept case fails).

**`tests/unit/testkit/test_fake_identity.py:55-58`** `test_no_account_answers_to_an_email_that_is_not_exact`,
`["ANN@example.org", "ann@example", "", "bot"]`; the fake is one equality (`testkit/fakes.py:315-320`):
one class. **Keep `"ANN@example.org"`** (a case-insensitive compare is the likely mistake), drop 3.

## 5. P-31's unit half

`tests/unit/services/test_documents.py:73-76`: `documents` is `params=["default_documents",
"flat_documents"]`, taken by **28 test functions** (about 60 cases with the 3-row `data` table).
The policy reaches `Documents` only in `parse` (`services/documents.py:314-318` minting parts,
`:349-360` `_named_subjects`: nested → "not inside" refusal; flat → named subjects claimed). The
graph-IRI refusal (`:353-354`) comes before the policy branch. `render`, `expand`, `frame`,
`internal_values`, `validate` and the `stored` fixture (`toy_mapper().to_graph(dune(BOOK))`) do not read it.

Depend on the policy (keep both): `test_a_body_that_describes_a_node_outside_the_aggregate_is_refused`
(`:221`, refused by a different branch per policy) and `test_what_the_service_returns_it_accepts_back`
(`:348`, a round trip through both `_named_subjects` branches). Already single-policy:
`:138`, `:148`, `:234`, `:241`.
**Decision:** rename the parametrised fixture `each_policy` (or similar) for those two; the other
26 take `default_documents`. Risk low (the flat minting stays covered by `:148`, `:241`).

`tests/unit/services/test_listing_query.py:199-206` hostile filter takes `shelf, view, policy`;
`policy` is `@pytest.fixture(params=POLICIES)` (`:85-93`), `shelf` depends on it (`:137`). The value
is bound as a literal whatever the IRI shape. **Decision:**
`@pytest.mark.parametrize("policy", [POLICIES[0]], indirect=True, ids=["default"])` on that one test.
The other tests of the file read `policy.book_iri(...)` and keep both.

## 6. `ToyService()` profile

Probes: `temp/paydown/profile_toy.py`, `profile_toy_start.py`, `probe_parts.py` (outputs `.out`).
Unprofiled, this machine: **ToyService() 0.09-0.11 s**, lifespan start+stop 0.02 s (the Debt's
0.24 s was a CI/xdist figure; the share holds).

Top cumulative costs (5 constructions, cProfile, 0.31 s each profiled):

| # | Function | cum per construction (profiled) |
|---|---|---|
| 1 | `install_service` (`entrypoints/service.py:32`) | 0.304 s |
| 2 | `ServiceKit.__init__` (`entrypoints/kit.py:94`) | 0.276 s |
| 3 | `Documents.__init__` (`services/documents.py:93`) → `Graph().parse(shapes)` | 0.113-0.141 s |
| 4 | rdflib Turtle parser (`notation3` `loadStream`/`statement`, 2983 shape triples) | ~0.13 s |
| 5 | `schema_structure.iri_types` (`:348`) on a fresh view | 0.131-0.152 s |
| 6 | linkml `SchemaView.imports_closure` (YAML load of ~16 imports) | 0.069 s |
| 7 | `owned_classes`/`owned_slots` → `induced_slot` | 0.061 s |
| 8 | `router.build_router` (`entrypoints/router.py:410`) incl. `openapi.add_to` | 0.027 s |
| 9 | lifespan (`service.py:166`): stamps, migrations, guard | 0.017 s (3 calls → 0.05 s/start) |
| 10 | `migrations.chain_of` x2 | 0.006 s |

Unprofiled parts (`probe_parts.py`): parse shapes **39 ms**; rebuild a Graph from a cached tuple of
the same triples with `addN` **7.5 ms**; `load_schema` + `iri_types` on a fresh view **38 ms**
(0.1 ms on a warm one); whole `ToyService()` **89 ms**.

What can be cached per process without sharing mutable state:
- **Shapes (recommended):** cache the parsed triples as an immutable tuple keyed by
  `(resolved path, mtime_ns, size)` (a `functools.cache`d function in `services/documents.py`),
  and give each `Documents` its own `Graph` built with `addN`. Saves ~31 ms of 89 (~35 %) in
  production and tests alike; no graph is shared. `test_validating_leaves_the_cached_shapes_unchanged`
  keeps guarding the per-instance graph. Risk low; the key covers generator tests that rewrite a
  shapes file in `tmp_path`.
- **Schema view:** not cacheable without sharing: `SchemaView` is mutable and code mutates class
  definitions (`schema_structure._set_required`); PD-2's sharing was measured as no saving. The
  frozensets `iri_types` returns are immutable, but caching them only moves the closure load to
  `Documents`, which reads the same view next. Leave it.
- Router/OpenAPI (9 %) and lifespan (15 %) are per-app work: leave them.

Expected effect: ~0.03 s × ~410 entrypoint tests ≈ 12 s serial (≈ a third of the set-up).

## 7. `event_bus_conformance` wait

`rdf_persistence/testkit/event_bus_conformance.py:50-54`: `Inbox.has` calls
`wait_until_async(probe, ...)` with the default `poll_seconds=POLL_SECONDS` (1 s,
`testkit/bootstrap.py:15`); `wait_until_async` (`bootstrap.py:67-98`) already takes and validates
`poll_seconds`, and **probes before it sleeps**. Callers: `tests/unit/testkit/test_in_memory_event_bus.py:27-29`
(in-memory delivers inside `publish`: the first probe succeeds, no sleep) and
`tests/integration/adapters/test_redis_events.py:43` (Redis, `claim_idle=500 ms`: each wait sleeps
in 1 s steps).

Change: `run_case(case, pair, *, poll_seconds=POLL_SECONDS)` passes it to the case; each case takes
`poll_seconds: float = POLL_SECONDS` and builds `Inbox(poll_seconds)`; `Inbox.has` passes it on.
Back-compatible (`case(pair)` still works); the Redis test passes e.g. `0.05`. Delta to `rp-testkit`.
Saving: Redis lane only (up to ~1 s per wait, 3 cases + the retention test); none in-memory.

## 8. Cross-test-module imports

Recomputed with an AST scan (`temp/paydown/cross_imports.py`, full list with names in
`cross_imports.out`): **79 import statements from 33 test modules** (the review's ~25 "older" ones
counted modules, not statements; the five the grooming added are now in helper modules).
Existing helper modules to extend: `tests/unit/services/migration_helpers.py`,
`collaboration_data.py`, `tests/unit/entrypoints/scene.py`, `listing_shelf.py`, `tenant_requests.py`,
`tests/integration/store/sessions.py`, `tests/integration/tenancy/file_stores.py`,
`tests/e2e/world.py`, `tests/unit/generation/golden.py`, `terms.py`.

Rule for the PLAN: constants and builders go to a helper module next to the users; fixtures that are
imported "for their side effect" (`# noqa: F401 (the fixtures)`) go to the folder's `conftest.py`.
A helper used across tiers (unit + integration + feature) goes to `tests/` root beside `toy.py`.

| Source test module (importers) | Names (most used) | Proposed home |
|---|---|---|
| `unit/services/test_tenant_sweep` (16, incl. integration and feature) | `make_world` x11, `CREATOR` x9, `TURTLE`, `BOOK_TYPE`, `HOUR`, `FILE_KEY`, `book`, `NOW`, `LOADED_AT`, `OWNED_BY`, `ALL_QUADS`, `FLAT`, `Events`, `EventFiles` | new `tests/tenancy_world.py` (cross-tier): `make_world`, `CREATOR`, `book`, `TURTLE`, `BOOK_TYPE`, `FILE_KEY`, clock constants, `Events`/`EventFiles` |
| `unit/services/test_session_activity` (10) | `activities` x7, `stored_graph` x5, `opened` x4, `B1-B3`, `book`, `PROVENANCE`, `Hook`, `X`, `ticking`, ... | new `tests/unit/services/activity_helpers.py` |
| `unit/services/test_tenant_dump` (6, incl. integration + feature) | `BASE_STAMPS` x4, `TOY_CHAINS` x3, `MANIFEST`, `VIEW`, `edited`, `iris_of`, `moved`, `dumped`, `restored`, ... (~40 names); used as fixtures by `test_restore_across_versions_adversarial` | new `tests/dump_helpers.py` (cross-tier) for builders/constants; its fixtures to `tests/unit/services/conftest.py` |
| `unit/entrypoints/test_service_kit` (4, incl. feature) | `made` x3, `installed`, `A_UUID` | `tests/unit/entrypoints/scene.py` (or `tests/toy_service.py` for `A_UUID`, as feature imports `made`) |
| `unit/generation/test_generate_cli` (4) | `project` x3, `SCHEMA`, `PYPROJECT` | `tests/unit/generation/golden.py` or new `generation/projects.py` |
| `unit/services/test_collaboration_cascade` (3) | `before` x3, `put`, `put_book`, `poetry`, ... | `tests/unit/services/collaboration_data.py` |
| `unit/services/test_collaboration_collections_adversarial` (2), `test_collaboration_workflow_adversarial` (2: `copy_schema`, `edit`), `test_collaboration_workflow` (1), `test_collaboration_discussion` (1), `test_collaboration_collections` (1: `poetry`) | collaboration builders | `collaboration_data.py` (schema-copy helpers: `copy_schema`, `edit` into a `schema_edits.py` if it grows) |
| `unit/services/test_session_unique_keys` (3) | `book`, `ISBN` | `activity_helpers.py` |
| `unit/services/test_pending_mark` (2, incl. feature) | `RESTORER`, `TOY_CHAINS`, `PLUMBING`, `three_commits` | `activity_helpers.py` (`TOY_CHAINS` from `dump_helpers`) |
| `unit/services/test_session_activity_adversarial` (1) | `KEYS`, `X`, `overtaken_commit` | `activity_helpers.py` |
| `unit/services/test_relay` (2, incl. feature) | `add_one`, `book`, `commit`, `pending`, `triples`, `RecordingOffer`, ... | new `tests/relay_helpers.py` (feature uses it) |
| `unit/services/test_migration_runner` (2, incl. integration) | `ISBN`, `LIB`, `chain_of`, `migration`, `rename`, `STAMPS`, ... | `tests/unit/services/migration_helpers.py` (move to `tests/` root if the integration import stays) |
| `unit/services/test_migrate_dataset` (1; fixtures `lib_chain`, `toolkit_chain`) | builders + fixtures | `migration_helpers.py` + `tests/unit/services/conftest.py` |
| `unit/services/test_migration_chain`, `test_migration_files` (1 each) | `SCHEMA`, `put`, `refused`, `migration`, `rename`, `step`, `write` | `migration_helpers.py` |
| `unit/services/test_messagebus` + `test_messagebus_wiring` (1 each) + `test_activity_shape` (1) | `Recorder`, `ShelvedReplace`, `fakes`, `World`, `world`, `framed`, `mapped`, ... | new `tests/unit/services/messagebus_helpers.py` |
| `unit/services/test_iri_policy_checks` (1), `test_tenancy` (1), `test_tenancy_stores` (1) | policy and tenancy builders | `iri_policy_helpers.py`, `tenancy_helpers.py` (one each, or one `tenancy_helpers.py`) |
| `unit/services/test_documents` (1) | `BOOK`, `BOOK_JSON`, `encoded` | `tests/toy.py` already holds book builders: put `BOOK_JSON` there or a `documents_helpers.py` |
| `unit/entrypoints/test_events_route` (1: feature) | `Follow`, `follow`, `listening`, `mount`, `replace`, `reshape_grants`, `with_carol`, `Block`, `another_book` | new `tests/events_follow.py` (cross-tier) |
| `unit/entrypoints/test_router` (1) | `_everyone_has_a_role` (private) | `scene.py` (made public) |
| `unit/generation/test_lock` (2), `test_freshness` (2), `test_boundary_check` (1) | lock and freshness builders | `tests/unit/generation/` helper modules (`lock_helpers.py`, `golden.py`) |
| `integration/store/test_session` (1) | `BEN`, `TENANT`, `book`, `session_for`, ... | `tests/integration/store/sessions.py` |
| `e2e/test_library` (1) | `LIBRARIAN`, `dune` | `tests/e2e/world.py` |

Guard: once empty, add a check (an import-linter `forbidden` contract or a 10-line test over
`ast`) that no module imports a `test_*` module; `cross_imports.py` is the template.
Risk: mechanical but wide (~40 files); do it with `ast-grep`, one source module per commit-sized step,
run `make test-fast` after each group.

## 9. Under-the-floor items

The final review's text for these items is not in the repository (design.md lists only the ids;
`session-trace.md` has no detail). Each line below is from the caller's gloss and what the code shows.

- **L3-S1 class-comment vocabulary:** `# Class:` 44 in 9 files; `# Equivalence class:` 20 and
  `# Equivalence classes:` 16 (36, in ~23 files); `# one case per class:` 3; prose "one class" 19.
  `testing.adoc` names no form. Change: one form, `# Class:` (`# Classes:` for several), rewrite the
  39 others with `ast-grep`/Grep, and name the form in `testing.adoc` rule 6.
- **L3-S5 tooling tests at `tests/unit` root:** 11 files. Repository tooling: `test_changed.py`,
  `test_check_docs.py`, `test_lanes.py`, `test_markers.py`, `test_no_polling_hook.py`,
  `test_refresh_map.py`, `test_adopt_validators.py` (docs listing) → `tests/unit/tooling/`.
  Package surface: `test_lazy_exports.py`, `test_packaging.py`, `test_public_api.py`, `test_smoke.py`
  → `tests/unit/package/`. Check `tests/changed.py`'s mapping and `tests/audit/scenario-map.csv`
  ids (`make refresh-map`) after the move; `Makefile:41` names `tests/unit/test_lanes.py`.
- **L3-S6 stage/task docstrings:** 19 references to a plan's task or stage numbers, meaningless
  once archived: `tests/toy_service.py:1`, `tests/e2e/test_library.py:1`,
  `tests/unit/entrypoints/test_openapi.py:1`, `test_router.py:661`, `test_negotiation.py:1`,
  `test_service_kit.py:1, :365, :431`, `tests/unit/domain/test_access_model.py:4`,
  `test_iri_policy_adversarial.py:1` (domain), `tests/unit/services/test_tenancy.py:440`,
  `test_tenant_dump_adversarial.py:3`, `test_tenant_stores_adversarial.py:1`,
  `test_iri_policy_minting.py:4`, `test_iri_policy_adversarial.py:1` (services),
  `tests/unit/testkit/test_fakes.py:70`, `tests/unit/generation/test_ext_pydantic_validators.py:330`,
  `test_generated_source_safety.py:1`, `tests/integration/store/test_mapper.py:1`
  (`grep -rnE "\b[Ss]tage [0-9]|\btask [0-9]+\.[0-9]+" tests`). Change: replace each with the
  capability/requirement or PD id it serves, or drop it.
- **L3-S9 rule-1 leftovers in `services`:** the import-linter contract guards `tests.unit.domain`
  (`.importlinter:180`). Left in `tests/unit/services/`: `test_tenant_move.py` tests
  `domain/tenant_move.py` but builds its `Iris` with `services.schema.load_schema` +
  `iri_types` (`:15-18, :44`), which is why `setup.cfg:20-23` adds it to the domain mutation
  selection. Change: build the `Iris` from literal type sets (frozensets) and move the file to
  `tests/unit/domain/` (then drop the `setup.cfg` line). `test_private_transaction_pieces.py` is an
  AST check of `services/` source (imports no package code): move with the tooling tests.
- **L2-S2 marker-table completeness:** `tests/unit/test_markers.py` checks each row
  (`:29`) but nothing checks that every test file falls under a row of `_MARKERS_BY_DIR`
  (`tests/conftest.py:80-93`). Change: one test: every `tests/**/test_*.py` gets non-empty
  `markers_for_path` (today all do; `tests/audit/` holds no test files).
- **L2-S3 Hypothesis `-n 2`:** `test_the_hypothesis_profile_is_derandomized_under_ci`
  (`test_markers.py:142-157`) claims "every xdist worker has it" but runs without xdist. Change:
  `runpytest_subprocess("-n", "2", ...)` with two test files, `assert_outcomes(passed=2)`.
- **L2-S7 default-clock aware timestamp:** `utc_now` (`services/session.py:315-316`,
  `datetime.now(UTC)`) is the default clock of `Tenancy`, `tenant_dump`, `FakeFileStore`, the events
  route; no test pins that it is aware (mutant `datetime.now()`). Change: one unit test,
  `utc_now().utcoffset() == timedelta(0)`.
- **L45-S4 `listing_shelf` model/personas:** `tests/unit/entrypoints/listing_shelf.py:12-19, :64-67`
  builds bodies as `{**DUNE_BODY, "label": ..., "genre": ...}` (bare dict, string keys: principle 2),
  and the personas `"ada"`, `"rita"`, `"omar"` are free strings (also in `scene.py:16`; `omar` is
  named in the docstring but unused here). Change: bodies through
  `body_of(dune_book(label).model_copy(update={...}))` with `Genre` members; persona constants in
  `tests/toy_service.py` (`ADA_SUB = "ada"`, ...) used by both helper modules.
- **L45-S5 conftest constants:** tests import from conftests, which are plugins:
  `tests.unit.services.conftest.GENERATED` (4 files), `tests/unit/generation/conftest.py`
  `TOY`, `ROOT_SCHEMA`, `Breaker` (9 files), `tests.integration.api.conftest.make_book` (1),
  `tests.conftest.TESTS_ROOT_DIR`/`markers_for_path` (2, fine: the code under test lives there).
  Dead: `tests/conftest.py:35` `TEST_DATA_DIR` (directory does not exist) and `load_text_file`
  (`:141`, no caller). Change: move the constants to `tests/toy.py` (`GENERATED`) and
  `tests/unit/generation/golden.py` or `terms.py` (`TOY`, `ROOT_SCHEMA`, `Breaker`); delete the dead pair.

## 10. Domain survivors (73 non-message: 57 none-arg + 16 logic)

Source `openspec/changes/test-debt-paydown/inputs/domain-survivors.md` (audit 2026-11-16, mutmut 3.8.1;
selection `setup.cfg:19-23`). **First step of stage 3: re-run `make mutation`**: the list predates the
final fixes, and `tests/unit/domain/test_iris_application_adversarial.py:223-272` already has
"shaped" policies for the application probes, so some below may be dead already. Default templates
(probed): tenant `{base}{tenant_segment}/{tenant_id}`, application `{base}app`, access/meta/
registry/provenance `{tenant}/<name>`, aggregate `{tenant}/{rp_path}/{id}`, part `{root}/parts/{id}`,
loaded `{root}/content/{id}`, principal `{issuer}/users/{sub}`; `_ANY = ".+"`; alphabet `0-9a-z`.

| # | Group (mutants) | n | Verdict | Killing test, or why equivalent |
|---|---|---|---|---|
| A | Module wrappers pass `""` → `None`: `aggregate_iri_2`, `mint_aggregate_iri_2`, `mint_part_iri_1`, `_3`, `loaded_graph_iri_1` (`domain/iris.py:94-170`) | 5 | **equivalent** | `DEFAULT_IRIS`'s templates write no `{type}` and the part/loaded ones no `{tenant}`; `_allow` only reads `cls_type` when `{type}` is in the template; `format` ignores unused keys |
| B | Message-only through `None` or a changed word: `root_of_graph_11`, `_new_id_5`, `tenant_5`, `aggregate_5`, `tenant_of_access_13`, `_require_distinct_graphs_of_18` (`taken[iri]` is read only in the message), `_of_28`, `_require_application_apart_3` (`IRIs`→`iris` in the text), `_21`; sparql `_literal_6`, `match_patterns_3`, `value_patterns_3`, `count_6`, `order_by_3`, `checked_group_25`, `term_10`, `term_13`, `_joined_3`, `_any_node_problem_7` (`IRI`→`iri`); `MessageLimitExceeded_1` | 20 | **equivalent (DEC-3)** | the exception class is unchanged; only its text differs and rule 9 forbids asserting text. (`MessageLimitExceeded_1`: `str(e)` becomes `"None"`; same reason) |
| C | Exception attributes, "no tests": `KeyConflict.__init__` 1-5, `MigrationFailed.__init__` 4-6, `MessageLimitExceeded.__init__` 2 (`domain/exceptions.py:52-56, 109-115, 163-165`) | 9 | **kill** | in `tests/unit/domain/test_exceptions.py`: `KeyConflict("m", iris=("a",), keys=["k"])` keeps `.args == ("m",)`, `.iris == ("a",)`, `.keys == ("k",)` (a tuple); `MigrationFailed(..., schema=, migration=, cause=)` keeps the three; `MessageLimitExceeded(3).limit == 3`. Services read them (`migration_runner._failure` logs `schema`, `migration`) |
| D | `tenant_resource_name` 5, 8 (`rsplit("/")`, `rsplit("/", 2)`) | 2 | **equivalent** | the last element after splitting at the last `/` is the same whatever the max split |
| D' | `tenant_resource_name_9` (`[-1]`→`[+1]`) | 1 | **kill** | an IRI with no `/` (e.g. a bare UUID or `"abc"`): original `InvalidIri` (or the name), mutant `IndexError` |
| E | `_differences_2` (`and`→`or`) | 1 | **kill** | `policy_differences(IriPolicy(), IriPolicy(tenant_id=IdSpec(kind=UUID4)))` lists `tenant_id`; the mutant recurses into `None` and raises. (Docstring asks for effective policies, where both are dicts; the test pins that a raw pair does not crash) |
| F | `draw_id_10` (`length or 0`→`or 1`) | 1 | **equivalent** | a random spec always has a length 4-32: `check_iri_policy` refuses one without (`iris.py:232-233`) and the model has `ge=4`; `draw_id` is never called with `length=None` on a random spec |
| G | `_alternation_2` (the `if types` condition; diff truncated) | 1 | **kill** | an `Iris` whose aggregate template writes `{type}` and has no root types: an IRI with an empty `{type}` is not an aggregate (original `(?!)` never matches; `(?:)` matches empty) |
| H | `_compile_20`, `_21` (backreference lost) | 2 | **kill** | a policy whose template repeats a variable (if `_check_template` allows; the branch exists for it): an IRI matches only when both occurrences agree; the mutants raise `TypeError` / `re.error` at compile |
| H' | `_compile_26` (no `re.DOTALL`) | 1 | **kill** | a tenant IRI holding `\n`: `is_aggregate(t, mint_aggregate(t, ...))` stays True (the `.+` tenant group crosses the newline only with DOTALL) |
| I | `Iris.__init__` 2, 3 (`deep=None/False`) | 2 | **kill** | build `Iris(settings)`, then change a nested field of `settings.iri_policy` (e.g. `part_template`): the `Iris` mints as before (PD-12f). A top-level change does not kill it (the shallow copy covers that) |
| J | `part_needs_type` 1, 2 ("no tests") | 2 | **kill** | `Iris(default).part_needs_type()` is False; with `part_template` writing `{type}` it is True |
| K | `_require_distinct_graphs` 1, 2 (tenant probe skipped / inverted) | 2 | **kill** | a policy where only a *tenant's* graphs coincide, not the application's: e.g. `tenant_template="{base}{tenant_id}"`, `application_template="{base}application"`, `meta_template="{tenant}/meta"`, `access_template="{base}{tenant_id}/meta"` → `InvalidIri` |
| L | `_require_distinct_graphs_of` 19 (`found=None`), 27 (`str(None)` tenant) | 2 | **kill** | `access_template="{tenant}/acl/{tenant_id}"` under default UUID ids: the access IRI reads as the tenant's own aggregate (`rp_path=acl`, `id=tenant_id`) → `InvalidIri`; both mutants accept it |
| L' | `_require_distinct_graphs_of_24` (`_belongs(found, None)`: stricter) | 1 | **timeboxed kill, else equivalent** | needs a graph IRI that reads as an aggregate of *another* tenant only; with `{tenant}`-prefixed templates every match belongs to its own tenant. Try a `{tenant_id}`-only aggregate template; if no legal policy produces it in 15 min, record equivalent |
| M | `_require_application_apart` 16, 17 (`None` for the tenant in `is_aggregate`/`is_loaded_graph`) | 2 | **kill** | a policy where a tenant reads as an application aggregate (16): `application_template="{base}{tenant_segment}"`, `aggregate_template="{tenant}/{id}"` (tenant = `{base}tenants/<uuid>` reads as application aggregate `<uuid>`); and one where it reads as an application loaded graph (17): same with `loaded_graph_template="{tenant}/{id}"`. Check the existing `TENANT_SHAPED_AGGREGATE` tests (`:223-245`) first: they may already be these |
| N | `_application_probes` 4, 8, 22, 23, 29, 30, 47, 50, 51, 52, 66 (a probe value or the probe itself replaced by `None`/the application) | 11 | **kill per probe kind; the root-only ones equivalent** | one test per kind where that probe reads as a tenant (the "aggregate", "loaded", "part" policies at `test_iris_application_adversarial.py:261-266` are the shape): kills 4, 8 (aggregate, id), 47, 51, 52, 66 (loaded), 30 (part type, with a `{type}` part template). 22, 23, 29, 50 (`root` replaced) only matter if a root-built IRI can read as a tenant; the tenant template has no `.+` group, so a `{root}`-prefixed probe cannot, while a template without `{root}` ignores it: **record 22, 23, 29, 50 as equivalent** after the re-run confirms they survive the per-kind tests |
| O | `_probe_types_2` (`or True`) | 1 | **kill** | a refused policy (e.g. M's) built with `root_types=frozenset()`: the original probes one type-less aggregate and refuses; the mutant probes none |
| P | `_reads_reserved` 1, 2 (`tenant_id` read as `None`) | 2 | **kill** | flat policy (`{tenant_id}` in the loaded/aggregate template): `is_loaded_graph(None, iri)` is False when the IRI's `tenant_id` is a reserved word other than `app` (e.g. the tenant segment) |
| Q | `principal_4` (`**self._fixed` dropped) | 1 | **kill** | a policy with `principal_template="{base}people/{sub}"`: `principal("iss", "ada")` mints under the base (mutant: `KeyError`). Default template uses no fixed variable |
| R | `tenant_move.check_graphs_22` (`is_loaded_graph(None, graph)`) | 1 | **kill** | a dump with a quad in a loaded graph of another tenant's aggregate (`iris.mint_loaded_graph(other, other_root)`) is refused; with `None` the root is not checked against the tenant |
| S | sparql `_string_13`, `_14` (`\u` after a backslash) | 2 | **kill** | `term(Literal("a\\u0041"))` == `"a\\\U000000750041"` (probed), or parse it back with rdflib and get `aA`. 13 drops the `u` (`re.sub` treats `None` as `""`, probed), 14 raises `TypeError` |
| T | `checked_group_7` (`_parsed(text, None)`) | 1 | **kill** | `checked_group("?s <urn:p> ?o FILTER(true)", template=True)` raises `SparqlError` (probed: an INSERT template cannot hold a FILTER; read as ASK it parses) |

Totals: **40 to kill** (C 9, D' 1, E 1, G 1, H 3, I 2, J 2, K 2, L 2, M 2, N 7, O 1, P 2, Q 1, R 1,
S 2, T 1), **1 timeboxed** (L'), **32 equivalent** recorded with the reason (A 5, B 20 under DEC-3,
D 2, F 1, N 4 root ones). 40 + 1 + 32 = 73. Groups C, J, R and S are the cheap, certain half (14 mutants).
