# Refresh A: facts 1-7, PD-1..7, 9, 10, 15, #215 S1-S3 on develop 030f580f

Read-only pass on 2026-11-21 against the thematic layout. Old paths are those in `facts.md` (be129a0).
Status: **still** = the debt is there as the PLAN says; **changed** = there, but the fix must change;
**gone** = nothing to do.

## PD-1 Monkeypatches of toolkit code (facts 1)

| Item | Now (file:line) | Status | Fix as written? |
|---|---|---|---|
| TC-37a `run_once` patch | `tests/unit/api/test_events_route.py:354-377` (patch :362) | still | yes, `async with kit.relay.paused():` (PD-2) |
| TC-38 `run_once` patch | `test_events_route.py:426-444` (patch :434), `test_an_id_never_relayed_sends_a_reset` | still | yes |
| TC-82 publish spy | `tests/unit/api/test_service_kit.py:686-704` (patch :692); hook `rdf_persistence/api/entrypoints/kit.py:236-240` (`if self.bus is not None` and then `relay.wake()`) | still | yes, drop the spy |
| migrate NOTHING | `tests/unit/tenancy/test_migrate_dataset.py:223-232` (patch :227) | still | yes, `Inert(Dataset)` beside `Failing` (:244-251). The runner now calls `dataset.update(prepare_update(...))` (`rdf_persistence/tenancy/services/migration_runner.py:162`), and an `update` override still catches it |
| migrate DROP_STAMPS | `:235-242` (patch :238) | still | yes, `Unstamping(Dataset)` |
| migrate SparqlError | `:263-275` (patch :273); call outside the try at `migration_runner.py:159`; `migration_request` at `rdf_persistence/migrations/services/migrations.py:232-242`, pattern check :290-296 | changed | The PLAN's "real data" route cannot go through `chain_of` (`tests/unit/tenancy/migration_helpers.py:37-43` → `load_chain`). `load_chain` refuses a bad step or request at load time (`migrations.py:88` `_step_problem`, `:90` `_request_problem`, which calls `migration_request` itself, `:314-324`). `Chain` is a plain tuple (`migrations.py:105`), so the test must build `((versions), (Migration(...),))` by hand with a `schema_id` holding a space. If it does not, the patch stays as exception 4 |
| adversarial CountingDataset | `tests/unit/tenancy/test_migrate_dataset_adversarial.py:188-212` (patch :199); `many_graphs` :178-185 builds through the `dataset(...)` helper | still | yes, but `many_graphs` must build a `CountingDataset` instead of calling `dataset()` (or `dataset()` must take a class). `assert small > 0` is still missing |
| generation_inputs x2 | now `tests/generator/unit/test_generation_inputs.py:199-209` (patch :205) and `:212-224` (patch :222); `generate(targets, base, steps, *, check)` unchanged at `rdf_persistence_generation/pipeline.py:217` | still | yes |
| freshness linkml version | `tests/generator/unit/test_freshness.py:182-188` (patch :185) | still | yes |
| freshness no-extra (kept) | `:191-207` (patch :201) | still | keep |
| freshness sha256 | `:424-440` (patch :431), `@pytest.mark.slow` | **changed** | It now zeroes `rp_api_entrypoints.yaml`, not `rp_service.yaml`. That is the toolkit's own `rdf_persistence/model/technical/api/rp_api_entrypoints.yaml`, which `toy_copy` does not copy (`tests/generator/unit/conftest.py:18-24`). "Append a comment to the copied file" cannot work without editing the real package. Change the data instead: rewrite that input's recorded hash in the copied manifest (through `GenerationManifest`) |
| receive KeyError (kept) | `tests/unit/api/test_receive.py:357-368` (patch :363) | still | keep |
| receive LookupError (kept) | `:371-382` (patch :377) | still | keep |
| `max_restore_bytes` (not debt) | `test_service_kit.py:451` | still | leave |

Where the exceptions are recorded: `docs/modules/ROOT/pages/develop/testing.adoc` has no monkeypatch rule
today. Its rule numbers are 1-2 Where, 3-4 Doubles, 5-10 Assertions, 11+ Time; rule 5 is "assert RDF by
isomorphism". The PLAN's "rule 5" and "rule 12" names do not match this page. The task that records the
three exceptions must say where they go (rule 3 "Prefer one fake...", `testing.adoc:44`, is the closest).

**Monkeypatches of toolkit code that are new since be129a0 and not in PD-1**
(`grep -rn "monkeypatch.setattr" tests/unit tests/generator/unit`, compared with `git grep` at be129a0):
- `tests/unit/api/test_toolkit_wiring_adversarial.py:60` `api.entrypoints.sse.event_stream` and `:83` `api.entrypoints.kit.tenant_dump.restore` (spies on the wiring).
- `tests/unit/api/test_shacl.py:27` `core.domain.sparql_parsing.SPARQL_PARSER_LOCK` and `:58` `api.services.shacl.validate`.
- `tests/unit/core/test_sparql_parsing.py:42` `SPARQL_PARSER_LOCK` and `:55` `sparql_parsing.<name>`.
- `tests/unit/collaboration/test_collaboration_collections_adversarial.py:659` `Mapper.max_roots` property. At be129a0 it patched `DEFAULT_MAX_ROOTS`, and PD-1 did not list it then either.
- `tests/unit/events/test_relay.py:601` `world.store.query`, a FakeStore instance. It follows the same pattern as :404/:429/:523/:556, which PD-1 also left out.
- `tests/unit/test_technical_split.py:248` `api.entrypoints.openapi.served_folders`.
- Generator: `test_generation_inputs.py:272` `manifest.SERVED_SCHEMAS`; `test_components_served.py:64,74,86` `components.SERVED_SCHEMAS`; `test_ext_typescript.py:172,225` `typescript.SERVED_SCHEMAS`; `test_hard_check.py:1241-1242` `TOOLKIT_ROOTS`; `test_ext_pydantic_split.py:158,630` `METAMODEL_DIR` and `:657` `TOOLKIT_ROOTS`; `conftest.py:81` `TOOLKIT_ROOTS` of every `ROOTS_USERS` module (the `toolkit_project` fixture). These are module constants used as configuration seams.
- Third-party or stdlib only, not toolkit code: `test_documents.py:415-416,482-483` (rdflib `Graph`/`Dataset.serialize`), `test_uml_qea.py:425` (`sqlite3.connect`), `test_refresh_map.py:194,335` (`subprocess.run`).
- Present at be129a0 but outside PD-1, unchanged: `test_router_hardening.py:140-141`, `generator/unit/test_roundtrip.py:65`, `iris/test_iris_application_adversarial.py:249`, `migrations/test_migration_files.py:252`, `testkit/test_fakes.py:240` (now `prepare_update`).

G-1 ("no monkeypatch of toolkit code in the unit tier except three") is false as worded: about 20 more
exist. Either narrow G-1 to the PD-1 list, or decide these. No fix is proposed here.

## PD-2 `Relay.paused()` (facts 1)

`rdf_persistence/events/services/relay.py`: `_lock` at :107, `run_once` at :126-131 (`async with self._lock`),
`wake` at :109, `run` at :113-124. There is no `paused()` (grep: none in the package, specs or tests). The
relay is built at `api/entrypoints/kit.py:224` and started by the lifespan at
`api/entrypoints/service.py:187`. **Still; the fix applies as written.** The constructor now takes
`events: EventSettings` (:93), not `interval=` or `publish_timeout=`.

## PD-3 Absence waits (facts 2)

**Gone in `test_events_route.py`** (PR #213, `open_event_stream`; no `take(` is left anywhere):
- default route: `test_the_default_route_is_served_with_the_link_and_no_event_before_a_commit` :197-207 commits a sentinel and asserts that the first event is a `Replace`.
- resume hides a2 (TC-37b): `test_a_resume_does_not_send_what_the_caller_may_not_read` :380-398 uses a sentinel.
- other tenant (TC-40): `test_the_follower_of_another_tenant_hears_nothing` :466-493 uses a sentinel.

Wall-clock waits left under `tests/unit/api` and `tests/unit/events`:
- `test_events_route.py:236-243` keep-alive after grant removal (`KEEP_ALIVE = 0.05`, :33, through `short_times` :89-98). This is PD-4.
- `tests/unit/events/test_relay.py:307-321` d18, `publish_timeout_seconds=0.05` and `wait_for(..., 5)` at :315. This is PD-4.
- `tests/unit/api/test_service_kit.py:746-760` `test_a_keep_alive_of_the_toolkit_settings_reaches_the_events_route`: keep-alive 0.05 s, `max_lifetime_seconds=0.001`, ended by the first wake. It is not in the PLAN. It is a positive wait for the timer, not an absence.
- `tests/unit/api/test_open_event_stream.py:96-101` `test_a_silent_stream_raises_a_timeout_naming_the_url`: an absence wait of `SHORT = 0.5` s (:18) that expects `TimeoutError`. It is new with #213 and tests the testkit's own timeout, so it is inherent.
- `tests/unit/events/test_event_stream.py:146,197,216,237,261,270,339`: `keep_alive=0.01` timers. These are positive waits.
- `test_relay_adversarial.py`: none ("nothing sleeps", :4).

## PD-4 Keep-alive and d18

- Keep-alive test: `test_events_route.py:236-243` on the `/fast` mount (`mount` :101-108 now takes `sse=SseSettings`, `clock=`). **Changed:** `keep_alive=0` is no longer accepted. `SseSettings.keep_alive_seconds` has `ge=0.001` (`rdf_persistence/api/entrypoints/generated/settings/rp_api_settings.py:74`). The smallest value is `mount(service, "/idle", sse=short_times(keep_alive_seconds=0.001))`. Today's 0.05 s costs one 0.05 s wait, so the gain is small.
- d18: `HangingBus` at `test_relay.py:294-304` (the other-tenant branch already calls `await super().publish`); test at :307-321. **Changed:** `publish_timeout=0` is not accepted. `EventSettings.publish_timeout_seconds` has `ge=0.001` (`rdf_persistence/events/services/generated/settings/rp_events_settings.py:67`) and is passed as `events=EventSettings(...)`. Use 0.001. The note about the non-suspending fake branch still applies: `InMemoryEventBus.publish` must not suspend.

## PD-5 Fuseki status >= 500 (facts 3)

**Changed location.** The mapping moved to the shared base `rdf_persistence/persistence/adapters/sparql_protocol.py`
`_raise_for_status` :100-125. The redundant branch is :105-106 (`>= INTERNAL_SERVER_ERROR` raises
`StoreUnavailable(f"{self.service} answered {status}")`), and the final `not is_success` at :124-125 raises the
same class and text. `FusekiStore(SparqlProtocolStore)` is at `fuseki.py:28` and is the only subclass.
Tests: `tests/unit/persistence/test_fuseki_store.py:186-200` `test_data_plane_statuses_map_to_errors`
(its comment at :190-191 says "500 stands for the whole `>= 500` class" and must change).
`test_sparql_protocol_store.py:134,146` and `test_fuseki_store_parity.py:36` ("Fuseki answered 500") name the
text. It is the same text after the removal, so they still pass. The facts' claim "no test names the text"
is now false but harmless. **The fix applies**; edit `sparql_protocol.py`, not `fuseki.py`.

## PD-6 Auth guard (facts 3)

`rdf_persistence/api/entrypoints/auth.py:38-41`, unchanged (scheme check plus `not token.strip()`).
Existing cases: `tests/unit/api/test_service_kit.py:104-116` (`[None, "Bearer", "Basic YWRhOnB3", "Bearer not.a.jwt"]`),
`test_kit_application.py:61`, `test_kit_require.py:47`. **The two PD-6 tests do not exist yet**: no valid JWT
sent as `Basic <jwt>`, and no `"Bearer "` against a permissive verifier stub. Still; the fix applies.

## PD-7 Shapes cache (facts 6)

`rdf_persistence/api/services/documents.py:106` `self.shapes = Graph().parse(folder / SHAPES_FILE)`, with no cache.
**New since the facts:** `:107-109` `warm_up(self.shapes)` (`rdf_persistence/api/services/shacl.py:48-57`, commit
fd97bb83) runs one full pyshacl validation under the parser lock on every `Documents` construction.
`tests/unit/api/test_shacl.py` (`test_documents_warm_up_when_built_and_validate_without_the_lock`) pins that
behaviour.

`inputs/probes/probe_parts.py` **no longer runs**: `ModuleNotFoundError: rdf_persistence.services`. The current
paths are `rdf_persistence.schema.services.schema` (`load_schema` :68),
`rdf_persistence.schema.services.schema_structure` (`iri_types` :433) and `rdf_persistence.api.services.documents`.
A copy with those imports, plus a `warm_up` timing (scratchpad only, not committed), gave on this machine:

| Part | ms |
|---|---|
| parse shapes (3202 triples) | 34.1 |
| rebuild from cached tuple (`addN`) | 18.7 |
| `Graph() + cached graph` | 9.7 |
| `load_schema` + `iri_types`, fresh view | 53.2 |
| **`warm_up(shapes)`** | **138.9** |
| **`ToyService()` median of 7** | **242.2** (runs 237-471) |

**Changed:** the baseline is now about 240 ms (was 89 ms). The PLAN's shapes-triples cache saves about 15-25 ms
(under 10 %), so G-6 (at least 25 %) cannot be met by PD-7 as written. Most of the cost is the repeated
`warm_up`: per `shacl.py`'s docstring, its effect (the first call of each parse action) is process-wide, so it
is redundant for shapes already warmed. Meeting G-6 needs the re-plan to decide on warming once per shapes
digest, which needs the `test_shacl.py` test above revised, or else to lower G-6. The probe file itself
needs its three imports updated.

## PD-9 P-20 rows (facts 4)

- `tests/unit/access/test_token_verifier.py`: `INVALID_TOKENS` :112-141, **still 28** names, used by
  `test_an_invalid_token_is_refused` :205-211. The dedicated algorithm tests are at :219-232, and
  `test_an_expired_token` is at :213.
- The jwks branches moved (`rdf_persistence/access/adapters/jwks.py`): missing :129, malformed :141,
  algorithm :144, no kid :146, PyJWT :181, claims model :185, non-finite :186-187, unusable sub :188-189,
  expired :190-191, not yet valid :193, unknown kid :211. **New branches** in `_bound_key`: :158 "algorithm
  does not match its key" and :162 "key does not fit its algorithm". The facts' table predates them. Check
  whether `hs256-with-the-public-key` still lands on :144: its test at :219-224 still matches "is not
  accepted", so yes.
- `UNUSABLE_SUBJECTS = ("", ".", "..")` is at `jwks.py:42`; it now includes `""`. It is covered by
  `tests/unit/access/test_jwks.py:415-421` `test_a_dot_or_empty_subject_is_refused` (the PLAN cited :379-385).
  That also backs dropping `empty-sub`.
- `tests/unit/testkit/test_fake_identity.py:55-58`: still `["ANN@example.org", "ann@example", "", "bot"]`.
- **Still; the fix applies**, with the line numbers above.

## PD-10 P-31 unit half (facts 5)

- `tests/unit/api/test_documents.py`: the parametrised fixture `documents` is at :84-85
  (`params=["default_documents", "flat_documents"]`); `default_documents` is :75 and `flat_documents` :80.
  **Changed count: 40 test functions** take `documents` now (was 28). The two to keep on both policies:
  `test_a_body_that_describes_a_node_outside_the_aggregate_is_refused` :234 and
  `test_what_the_service_returns_it_accepts_back` :359. Already single-policy: :150, :160, :245, :252.
  So about 38 move to `default_documents` (PLAN: 26).
- The policy reaches `Documents` in `parse` :175ff. `part_needs_type` is at :326, `_named_subjects` at :357/:361.
- `tests/unit/persistence/test_listing_query.py`: `POLICIES` :84-87, the `policy` fixture :90-93, `shelf` :138.
  The hostile filter is now `test_a_hostile_filter_value_matches_nothing_and_leaves_the_store_unchanged`
  :212-220, and the fix applies. A sibling has appeared:
  `test_a_hostile_contains_text_matches_nothing_and_leaves_the_store_unchanged` :222-234 (6 texts × 2 policies),
  where the same argument holds (a bound literal). Flag it for the re-plan; no new scope is proposed here.

## PD-15 Conformance poll (facts 7)

`rdf_persistence/testkit/event_bus_conformance.py`: `Inbox` :38-54, with `has` → `wait_until_async(probe, ...)`
at :54 and no `poll_seconds`. `run_case(case, pair)` is at :106-113 and the cases at :60, :73, :88.
`POLL_SECONDS = 1` is at `testkit/bootstrap.py:15`, and `wait_until_async` at :67. Callers:
`tests/unit/testkit/test_in_memory_event_bus.py:27-29` and `tests/integration/adapters/test_redis_events.py:47-49`
(`RedisPair(..., claim_idle_seconds=0.5)`). The Redis file also polls at the default in :75 (retention) and
:156 (warned). **Still; the fix applies.**

## Issue #215 S1-S3 (`gh issue view 215` was refused: unauthenticated; read from the brief)

- **S1**: `test_a_resume_sends_what_was_relayed_after_the_id_then_live_events_none_twice` (TC-37),
  `test_events_route.py:336-351`. It still uses `events=3` (:345) and one live replace "Four" (:347), so "none
  twice" is only checked up to the third event. **Open.**
- **S2**: `test_a_resume_does_not_send_what_the_caller_may_not_read` (TC-37b), :380-398. It resumes from
  `a2` (:390), and `a2` is the hidden replace itself (:387-389). The replay therefore never contains a hidden
  activity to filter; only the live "Hidden again" (:392) is filtered. **Open.**
- **S3**: `test_the_default_route_is_served_with_the_link_and_no_event_before_a_commit` :197-207 asserts only
  `first.event == "Replace"` (:207), not the sentinel's generation entity (`settled.book_iri`). In
  `tests/unit/api/test_open_event_stream.py:54-79`,
  `test_one_event_is_returned_with_the_activity_iri_as_its_id` checks only `event.event` and the id (:78-79),
  not the event's data against the book. **Both open.**
