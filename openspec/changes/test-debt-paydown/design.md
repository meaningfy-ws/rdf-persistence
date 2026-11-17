<!-- PLAN (design half) of test-debt-paydown. PLAN = this file + tasks.md.
     Facts with file:line for every item: inputs/facts.md (read-only probe, develop be129a0). -->

# Design: test-debt-paydown

## Context

The test-suite grooming (archived `2026-11-16-test-suite-grooming`) left a *Debt* list and
"under the floor" review findings, and the domain mutation run left 111 survivors (38 change only
a message; 73 change behaviour). A read-only fact-finding pass (`inputs/facts.md`) settled each
item against the code. Two findings changed the EPIC: no relay fake or recording bus is needed (a
public `Relay.paused()` is enough, `RecordingObserver` + `bootstrap()` already records), and the
real-time waits need no clock parameter (every interval is already injectable or unneeded).

Constraints: the layering and `make` gates of `AGENTS.md`; the testing rules of
`develop/testing.adoc`; nothing generated is edited by hand; no new test library.

## Goals / Non-Goals

**Goals**
- G-1: no monkeypatch of toolkit code in the unit tier except the three recorded exceptions (PD-1).
- G-2: no test waits on wall-clock time for an absence (PD-3, PD-4).
- G-3: no test module imports another test module, and a test guards it (PD-8).
- G-4: every behaviour-changing domain survivor is killed or recorded as equivalent with its
  reason (PD-12); `make mutation` shows no unexplained survivor.
- G-5: the `rp-messages` spec says what the code does about an empty commit (DEC-1).
- G-6: `ToyService()`'s median construction time drops by at least 25 % (PD-7).

**Non-Goals**
- Widening `make mutation` beyond `domain/` (the EPIC's optional step is dropped: PD-13).
- Rewriting adversarial files; adding a test library; changing any public behaviour (PD-5 removes a
  branch without changing an outcome; PD-6 changes no code).

## Decisions

- **PD-1 Rule-5 monkeypatches** (facts 1). Replace:
  - `test_events_route.py` TC-37a, TC-38: `async with kit.relay.paused():` (PD-2);
  - `test_service_kit.py` TC-82: drop the `MessageBus.publish` spy; keep `kit.bus is None`, the
    write's success and "the commit is recorded";
  - `test_migrate_dataset.py` NOTHING / DROP_STAMPS: `Inert(Dataset)` / `Unstamping(Dataset)`
    subclasses beside the existing `Failing(Dataset)`;
  - `test_migrate_dataset.py` SparqlError: real data in this order: a step whose pattern fails its
    check (`migrations.py:235, :293`), else a `schema_id` holding a space (`Migration.schema_id` is a
    plain `str`); the test asserts the error comes from `migration_request` (not `stamp_problems`
    or `_held`). Only if neither reaches it does the patch stay, recorded as exception 4;
  - `test_migrate_dataset_adversarial.py`: `CountingDataset(Dataset)` built by `many_graphs`, plus
    `assert small > 0`;
  - `test_generation_inputs.py` x2: call `generate(read_targets(...), base, (step,), check=False)`;
  - `test_freshness.py` linkml version / sha256: edit the copied manifest (through
    `GenerationManifest`) / append a comment line to the copied `rp_service.yaml`.
  Keep, as recorded exceptions in `testing.adoc` (one sentence each): `test_receive.py` KeyError
  ("a defect inside toolkit code no port can produce"), `test_receive.py` LookupError ("a
  configuration the toy schema cannot have"), `test_freshness.py` no-extra ("an absent optional
  dependency").
- **PD-2 `Relay.paused()`** (`services/relay.py`): an `asynccontextmanager` that holds `_lock`; a
  wake-up during the block runs one round after it. The lock is not reentrant: calling
  `run_once()` inside the block hangs, which its docstring says. TC-38 follows and takes inside
  the block (after it, the woken round relays the pending id). Spec: `rp-events` ADDED
  requirement. Its unit tests in `test_relay.py` cover the three scenarios (held, resumed,
  released on exception).
- **PD-3 Absence waits** (facts 2): each `take(1, timeout=…)` that expects `TimeoutError` becomes
  "the next event is a later, visible one" (a sentinel commit after the hidden one): default route
  (`:258`), resume hides a2 (`:441`), other tenant (`:521`).
- **PD-4 Keep-alive and d18**: the grant-removed test mounts its own route with `keep_alive=0`;
  `test_relay.py` d18 uses `publish_timeout=0` and `HangingBus`'s other-tenant branch records
  without awaiting (a comment says why it must not suspend). No production change.
- **PD-5 Fuseki** (`adapters/fuseki.py:46-59`): remove the `status >= 500` branch; the final
  `not is_success` branch raises the same error with the same text.
- **PD-6 Auth** (`entrypoints/auth.py:38-41`): keep both halves and add the tests they lack: a
  valid token sent as `Basic <jwt>` is a 401 (the scheme half), and `"Bearer "` with a verifier
  stub that accepts any string is a 401 (the empty-token half). The empty-token half stays because
  `TokenVerifier` is a public port and a consumer's verifier is never held to the conformance
  matrix's `"empty"` case (it lives in `tests/`, not the testkit).
- **PD-7 `ToyService()` cost** (facts 6): in `services/documents.py`, an `lru_cache(maxsize=8)`
  `_shape_triples(digest) -> tuple` of the parsed shapes, keyed by the SHA-256 of the file's bytes
  (read each time; mtime is too coarse for a same-size rewrite); each `Documents` builds its own
  `Graph` with `addN`. No graph or schema view is shared. Acceptance: the median of 7 runs of
  `inputs/probes/probe_parts.py`'s `ToyService()` timing, before and after, on one checkout and
  machine, drops by at least 25 %.
- **PD-8 Cross-test imports** (facts 8, full list `inputs/probes/cross_imports.out`): constants and
  builders move to helper modules beside their users; fixtures imported for their side effect move
  to the folder's `conftest.py`; a helper used across tiers goes to `tests/` root. One home per
  source module (the 33 of `cross_imports.out`; ✱ = imported from another tier):

  | Source test module | Home |
  |---|---|
  | `unit/services/test_tenant_sweep` ✱ | `tests/tenancy_world.py` (new) |
  | `unit/services/test_tenant_dump` ✱, `test_pending_mark` ✱ | `tests/dump_helpers.py` (new); fixtures to `tests/unit/services/conftest.py` |
  | `unit/services/test_relay` ✱ | `tests/relay_helpers.py` (new) |
  | `unit/entrypoints/test_events_route` ✱ | `tests/events_follow.py` (new) |
  | `unit/entrypoints/test_service_kit` ✱ | `tests/toy_service.py` (`made`, `installed`, `A_UUID`) |
  | `unit/services/test_migration_runner` ✱, `test_migration_chain`, `test_migration_files`, `test_migrate_dataset` | `tests/migration_helpers.py` (the existing `tests/unit/services/migration_helpers.py` moves there); fixtures `lib_chain`, `toolkit_chain` to `tests/unit/services/conftest.py` |
  | `unit/services/test_session_activity`, `test_session_activity_adversarial`, `test_session_unique_keys` | `tests/unit/services/activity_helpers.py` (new) |
  | `unit/services/test_messagebus`, `test_messagebus_wiring`, `test_activity_shape` | `tests/unit/services/messagebus_helpers.py` (new) |
  | `unit/services/test_iri_policy_checks`, `test_tenancy`, `test_tenancy_stores` | `tests/unit/services/tenancy_helpers.py` (new) |
  | `unit/services/test_documents` | `tests/toy.py` (`BOOK`, `BOOK_JSON`, `encoded`) |
  | `unit/services/test_collaboration_cascade`, `_collections`, `_collections_adversarial`, `_discussion`, `_workflow`, `_workflow_adversarial` | `tests/unit/services/collaboration_data.py` |
  | `unit/entrypoints/test_router` | `tests/unit/entrypoints/scene.py` (`everyone_has_a_role`, made public) |
  | `unit/generation/test_lock` | `tests/unit/generation/lock_helpers.py` (new) |
  | `unit/generation/test_generate_cli`, `test_freshness`, `test_boundary_check` | `tests/unit/generation/golden.py` |
  | `integration/store/test_session` | `tests/integration/store/sessions.py` |
  | `e2e/test_library` | `tests/e2e/world.py` |

  Then a guard: `tests/unit/tooling/test_no_cross_test_imports.py`, an `ast` scan of every
  `tests/**/*.py` (helpers and conftests too) failing on `import tests.….test_x`,
  `from tests.….test_x import …` and `from tests.… import test_x`; its own test plants all three
  forms (template `inputs/probes/cross_imports.py`, which scans less).
- **PD-9 P-20 rows** (facts 4): `test_token_verifier.py` `INVALID_TOKENS` 28 → 17 per the facts'
  table (no `sub-dot` case: `test_jwks.py:379-385` already covers `UNUSABLE_SUBJECTS`);
  `test_fake_identity.py` email test keeps `"ANN@example.org"` only. Each drop is confirmed by a
  hand mutation of its branch that the kept case catches (recorded in the commit body).
- **PD-10 P-31 unit half** (facts 5): `test_documents.py`'s parametrised fixture becomes
  `each_policy_documents`, taken only by the outside-node refusal (`:221`) and the round trip
  (`:348`); the other 26 tests take `default_documents`. `test_listing_query.py` hostile filter:
  `@pytest.mark.parametrize("policy", [POLICIES[0]], indirect=True, ids=["default"])`.
- **PD-11 Under-the-floor items** (facts 9), all as stated there: one comment form `# Class:` /
  `# Classes:` named in `testing.adoc`; tooling tests to `tests/unit/tooling/` (with
  `test_private_transaction_pieces.py`), package tests to `tests/unit/package/`, `Makefile` and
  `tests/changed.py` paths updated, `make refresh-map` run; the 42 plan-number docstrings replaced
  by the requirement or PD they serve; `test_tenant_move.py` builds its
  `Iris` from literal type sets, its vocabulary terms as literal `URIRef`s (no
  `services.vocabulary`) and its settings in the test (no `tests.toy` `SETTINGS`/`TOY_SCHEMA`), and
  moves to `tests/unit/domain/` (and its `setup.cfg` line goes); a marker-completeness
  test; the Hypothesis profile test under `-n 2`; a `utc_now()` awareness test; `listing_shelf`
  bodies through the models with `Genre` members and persona constants in `tests/toy_service.py`;
  conftest constants moved (`GENERATED` → `tests/toy.py`, `TOY`/`ROOT_SCHEMA`/`Breaker` →
  `tests/unit/generation/golden.py`); `TEST_DATA_DIR` and `load_text_file` deleted.
- **PD-12 Domain survivors** (facts 10): first re-run `make mutation` and work from its list. Kill
  groups C, D', E, G, H, H', I, J, K, L, M, N (7), O, P, Q, R, S, T with the tests the facts name,
  in `tests/unit/domain/` (`test_exceptions.py`, `test_iris*.py`, `test_tenant_move.py`,
  `test_sparql*.py`; task 3.2 owns `test_exceptions.py`, `test_sparql*.py`, `test_tenant_move.py`,
  task 3.3 owns `test_iris*.py`). L' gets 15 minutes, then is recorded equivalent if no legal policy kills it.
  Record as equivalent, each with its one-line reason, in `tests/audit/equivalent-mutants.md`: A
  (5), B (20, DEC-3), D (2), F (1), N root-only (4), L' if so, and the 38 kind-`message` mutants
  of `inputs/domain-survivors.md` under one DEC-3 heading. A mutant the re-run no longer lists
  needs nothing.
- **PD-13 No services mutation**: the EPIC's "widen if time allows" is dropped; it is not needed for
  any goal and would make the stage's end open.
- **PD-14 Merge**: as DEC-2 (one PR, CI green on the PR before the merge). The owner, who said
  earlier to ignore GitHub runs, was asked at the PLAN gate and may overrule it; until then DEC-2
  holds, because stage 1 moves test folders and lanes.
- **PD-15 Conformance poll** (facts 7, `rp-testkit` delta): `run_case(case, pair, *,
  poll_seconds=POLL_SECONDS)` passes it to each case, which builds `Inbox(poll_seconds)`; `Inbox.has`
  passes it to `wait_until_async`. Its test, `tests/unit/testkit/test_event_bus_conformance_poll.py`,
  wraps the in-memory pair in a `DelayedPair` that delivers 0.1 s after `publish`, and asserts a
  delivery case passes in < 1 s with `poll_seconds=0.02`; a second test runs `run_case(case, pair)`
  unchanged. `tests/integration/adapters/test_redis_events.py` passes `poll_seconds=0.05`.

## Algorithm / approach

Three stages, one branch `change/test-debt-paydown-build`, one PR at the end; builders in
worktrees the lead creates (`git worktree add temp/wt/<task> <sha>`), one task each, disjoint
files; the lead cherry-picks.

- **Stage 1 (tests only):** PD-1 (except the `Relay.paused()` users), PD-3, PD-4, PD-8, PD-9,
  PD-10, PD-11. PD-8 and PD-11's moves go first and alone (they touch many files); then 1.3, 1.4
  and 1.5 in parallel; then 1.6 alone (it shares `testing.adoc`, `test_service_kit.py`,
  `test_documents.py` and `test_migrate_dataset_adversarial.py` with them).
- **Stage 2 (production + its tests):** PD-2 and its two users, PD-5, PD-6, PD-7, PD-15, DEC-1's spec.
- **Stage 3 (mutation):** PD-12.

Worked example (PD-3, default route): before, `bob.take(1, timeout=0.2)` must time out after the
hidden replace. After: `await listening(hub, 1)` (bob is subscribed; `n=2` where a witness also
follows, as in TC-37b), then the test replaces a book bob may read, `event = await bob.take(1)`,
and asserts it is that replace (the hidden one, committed first, would have arrived first: the
stream subscribes before it resumes and its queue is FIFO).

Worked example (PD-12, group J): `assert not Iris(settings).part_needs_type()` with the default
policy, and `assert Iris(settings_with(part_template="{root}/parts/{type}/{id}")).part_needs_type()`.

### Anti-patterns
- Replacing a monkeypatch with a new fake class of toolkit code (PD-1 uses real seams only).
- A sentinel event that could arrive before the hidden one (PD-3: commit it after).
- Moving a test into a lane CI does not run (every move here stays in the unit lane).
- A "killing" test that asserts message text (rule 9; DEC-3).
- Mass rewrites with `sed -i`, heredocs or scripts; edits go through Edit, Serena or `ast-grep`.

## Error matrix

| Failure | Detected by | Handling |
|---|---|---|
| A moved test is no longer collected, or its map row is lost | `make refresh-map` exit 1 (an id unmapped) or 2 (collection failed), "Removed rows" > 0; the count in `make test-fast` | the move task rewrites the map's paths first, then fixes paths before commit |
| A cross-import guard false positive (a `tests/**/test_*.py` helper import) | the guard's own unit test with a helper and a test module | the guard names the module; rename the helper |
| `Relay.paused()` never released, or `run_once()` called inside it (the lock is not reentrant) | pytest-timeout 120 s, signal method | the test fails naming itself; the docstring warns |
| A sentinel committed before the subscriber listens | `take(1)` times out (3 s) | `await listening(hub, n)` before the sentinel (PD-3) |
| `keep_alive=0` spins the stream | the test's wall time (< 1 s) | it is a dedicated mount; no other test uses it |
| Shapes cache returns stale triples after a file rewrite | task 2.4's test: two same-size rewrites in `tmp_path`, each `Documents` sees its own shapes | the key is the content digest, not the mtime |
| A root-package change selects no test in `make test-changed` (rule 11 globbed `tests/unit/test_*.py`) | `tests/unit/tooling/test_changed.py` | 1.1 maps rule 11 to `tests/unit/package/` |
| A kept P-20 case no longer guards a dropped one's branch | the hand mutation in PD-9 | keep the dropped case |
| A survivor's "killing" test does not kill it | the stage-3 re-run of `make mutation` | fix the test; no survivor is left unexplained |
| CI slower than local after the moves | the PR's CI run | PD-14: no merge until it passes |

## Risks / Trade-offs

- **RISK-1** (medium likelihood, low impact): PD-8 is wide (~40 files); a missed import breaks
  collection. Mitigation: one source module per step, `make test-fast` after each, the guard last.
- **RISK-2** (low, medium): the `Dataset` subclasses (PD-1) are not walked by rdflib's SPARQL engine
  the way the patch was. Mitigation: `assert small > 0` makes a vacuous count fail.
- **RISK-3** (low, medium): a consumer's `TokenVerifier` accepts an empty token. Mitigated by
  PD-6 keeping the entrypoint's empty-token guard, now tested with a permissive verifier stub.
- **RISK-4** (medium, low): fewer than 40 survivors die (a facts recipe is wrong). Mitigation:
  each one either gets a corrected test or an equivalence line with its reason; G-4 is "explained",
  not "zero".

## Open Questions

None open. OQ-1 (wait for the PR's CI before merging) was answered by the owner on 2026-11-17:
"keep CI wait" (PD-14 holds).

## Delivery decisions

(Filled during delivery.)
