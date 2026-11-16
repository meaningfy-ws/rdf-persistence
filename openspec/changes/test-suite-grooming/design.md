<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: EPIC `test-suite-grooming` (proposal.md); the audit
> `tests/audit/report-2026-11-16.md` (proposal ids P-n and the *Broken rules* tables) and
> `tests/audit/slow-markers.md`. Report rows are located by **file and function name**: their
> line numbers go stale as earlier stages edit the files.

## Context

Measured on 2026-11-16 (the *before*): `make test` 7,357 passed / 18 skipped, ≈ 214 s with
coverage; run A 123 s wall, set-up 0.46 of the unit summed time; containers 267 passed, 311 s;
18 tests ≥ 2 s alone without `slow`, 9 marked `slow` under 0.5 s; mutation of `domain/` 974 of
1,085 killed. Costliest fixtures: `service`, `scene`, `bootstrapped`, `world`, `shelf`, `books`.

## Goals / Non-Goals

**Goals:** DEC-1 to DEC-5 and every approved proposal. **Non-Goals:** the EPIC's No-gos.

## Anti-patterns (each a reason to stop the task)

| Anti-pattern | Why | Instead |
|---|---|---|
| Removing or changing a survivor case or survivor function | it is the guard that stays | survivors are listed in the report's Survivor column and in PD-10; never edit them in stage 2 |
| Merging cases across equivalence classes | loses a behaviour | merge only within the group the report row names |
| Changing an assert's condition in stage 5 | stage 5 is messages only | a split of a tuple assert keeps every condition; nothing else changes |
| Editing anything under `generated/` | generated from LinkML | change the schema and `make generate` (not needed in this EPIC) |
| Touching `test_messagebus_adversarial.py::test_an_empty_commit_does_not_spend_the_command_for_the_real_one_after_it` | DEC-5: open spec question | leave the function as it is; other functions of the file may change |
| Sharing a mock, or widening a fixture a test changes | isolation | widen only what the audit reading says no test changes |
| A drop with no named survivor | class 3 rule | the commit body names the survivor |

## Decisions

### Stage 1: set-up and libraries (class 1)

Task order: PD-9, PD-7, PD-1, PD-2, PD-3, PD-4, PD-5, PD-8, PD-6 (PD-7 decides the dist mode
PD-3 depends on; PD-6 re-times after PD-1).

- **PD-9 (libraries)**:
  - `pytest-timeout==2.4.0` in the `test` group; `pytest.ini`: `timeout = 120`,
    `timeout_method = thread`, `timeout_func_only = true` (fixture set-up, e.g. container start,
    is not counted); `timeout-minutes: 30` on every job of `.github/workflows/ci.yaml`.
    Verified by a pytester test in `tests/unit/test_markers.py`: a test that sleeps past a
    1 s `timeout` mark fails naming itself, and the next test runs.
  - `pytest.ini` registers `quarantine: passes and fails on unchanged code; carries an issue link
    (rule 14)`. Every Makefile lane that selects `-m "unit"`, `"feature"`, `"unit or feature"`
    or `"integration or e2e"` (`test`, `test-unit`, `test-feature`, `test-fast`, `test-changed`,
    `coverage-report`, `profile-tests`, `test-containers`, `test-e2e`) adds `and not quarantine`.
    Verified by a unit test that reads the Makefile and checks each of those recipes.
  - The Hypothesis profiles move unchanged from `tests/unit/generation/test_roundtrip.py` to
    `tests/conftest.py` (registered and loaded at import of the root conftest, so on every xdist
    worker). Verified by a unit test: with `CI=1`, `hypothesis.settings.default.derandomize` is
    true inside a test.
  - `mutmut==3.8.1` in the `dev` group. Root `setup.cfg`, section `[mutmut]`:
    `source_paths = rdf_persistence`; `do_not_mutate = rdf_persistence/*/generated/*` and
    `rdf_persistence/domain/generated/*`; `also_copy` = `docs`, `openspec`, `.claude/hooks`,
    `pytest.ini`, `.coveragerc`, `VERSION`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `Makefile`;
    `only_mutate = rdf_persistence/domain/*`;
    `pytest_add_cli_args_test_selection = tests/unit/domain`;
    `pytest_add_cli_args = -p no:cacheprovider -q`. Target `make mutation` (no arguments: mutmut
    3.8.1 reads its selection only from the config file) runs `mutmut run` then `mutmut results`;
    another layer is audited by editing the two selection lines locally. The spec delta's
    scenario is worded for the domain defaults.
    `make mutation` run on 2026-11-16 (task 1.1, 1 m 13 s): 1,085 mutants, **974 killed**, **94
    survived**, **17 untested** (no test reaches them); no timeouts or suspicious mutants.
    Same figures as the audit's before-count (974 of 1,085).
  - `polyfactory` leaves the `test` group (DEC-4); `uv lock`. The deviation from checklist rule 6
    is written as one line in `docs/modules/ROOT/pages/develop/testing.adoc` (model objects come
    from the named builders of `tests/toy.py`, validated by the models).
  - `pytest-randomly` trial: `uv run --with pytest-randomly==5.1.0 pytest tests --ignore=tests/integration --ignore=tests/e2e -n auto -m "unit or feature" -p randomly --randomly-seed=1`
    and again with `--randomly-seed=2`. Green twice: add `pytest-randomly==5.1.0` to the `test`
    group (the `-p no:randomly` in `profile-tests` stays meaningful). Any failure: do not adopt;
    delete the dead `-p no:randomly` flags (Makefile `profile-tests`, `tests/unit/test_markers.py`)
    and record each failing test id in this file under *Order dependence* for task 4.5.
- **PD-7 (P-7)**: Time `make test-fast` twice with the default `load`, twice with `--dist
  loadgroup` and twice with `--dist worksteal` (through `PYTEST_ADDOPTS`). Adopt the fastest mean
  in the Makefile's `-n auto` lanes; record the six times here. If `worksteal` wins, PD-3 is
  skipped (it needs `loadgroup`) and recorded as such.
- **PD-1 (P-1)**: In `tests/unit/generation/test_lock_step.py`, a session-scoped fixture
  `bootstrapped_template` copies the toy fixture tree into `tmp_path_factory`, removes the lock
  and runs the generator once (what `bootstrapped` does today); `bootstrapped` copies the template
  over `toy_copy` (`shutil.copytree(..., dirs_exist_ok=True)`) and returns the same `Toy`. Check:
  run the file twice, then its node ids in reverse order (`pytest $(pytest --collect-only -qq … |
  tac)`).
- **PD-2 (P-2)**: `ServiceKit(schema=...)` (`rdf_persistence/entrypoints/kit.py`) and
  `install_service(app, schema=...)` (`service.py`) accept `Path | SchemaView`; a view is used
  as given, a path is loaded as today. Test first in `tests/unit/entrypoints/`: a kit built from a
  view holds that view (`kit.view is view`); one built from the path holds an equal schema.
  `tests/toy_service.py` gains `@functools.cache def toy_view() -> SchemaView`; `ToyService`
  passes it when `schema` is the default `TOY_SCHEMA`.
- **PD-3 (P-3)** (only if PD-7 chose `loadgroup` or `load`; with `load`, the lanes switch to
  `loadgroup`, which behaves as `load` plus groups): the 44 read-only tests of
  `tests/unit/entrypoints/test_listing_routes.py` move into a class `TestReadOnlyListing` in a
  new `test_listing_routes_read.py`, the class decorated `@pytest.mark.xdist_group("listing_read")`
  and `@pytest.mark.asyncio(loop_scope="class")`, with class-scoped `service`, `client` and
  `shelf` fixtures (`loop_scope="class"`). Class decorators, not a module `pytestmark` (pytest.ini
  forbids per-file `pytestmark`). The 5 writers stay. The class's last test asserts the shared
  store still holds the five books and one tenant.
- **PD-4 (P-4)**: The `books` fixtures of `tests/unit/services/test_collaboration_discussion.py`,
  `test_collaboration_discussion_adversarial.py` and `test_collaboration_workflow.py` (lead,
  during 1.7: `test_collaboration_collections_adversarial.py` has no `books` fixture and is out
  of scope) build the books' triples in a module-scoped
  fixture and keep the `add_graph` writes per test; a test that asserts on a part IRI minted by
  `dune()` reads it from the shared triples.
- **PD-5 (P-5)**: `rdf_persistence.testkit` gains `shared_key()` (process-cached RSA key, moved
  from `tests/toy_service.py:toy_key`, which then calls it); the `signer` fixtures of
  `tests/unit/adapters/test_jwks.py` and `tests/unit/services/test_token_verifier.py` use it, except
  tests that need a second key (rotation, unknown `kid`): they build their own.
- **PD-8 (P-8)**: `wait_until` and `wait_until_async` (`rdf_persistence/testkit/bootstrap.py`)
  take `poll_seconds: float = POLL_SECONDS`; callers under `tests/unit/` and `tests/feature/` that
  wait on in-process fakes pass `poll_seconds=0.01`; container callers keep the default.
- **PD-6 (P-6)**: After PD-1, re-time the 18 tests of `tests/audit/slow-markers.md` alone
  (`pytest -p no:xdist --durations=0 <ids>`); add `@pytest.mark.slow` to each still ≥ 2 s; remove
  it from the 9 listed tests. Update the file with the new times.

### Stage 2: merged cases (class 2)

- **PD-10**: Each P-20 … P-34 row merges its listed groups. Where the row names the survivor
  cases, keep exactly those; otherwise "keep N" keeps the first N values as listed in the source
  today, "keep 1–2" keeps 2, "about 3 (per X)" keeps 3 (per X), "one per group" keeps 1 per
  group; P-26 keeps one form per other layer plus the full form axis on `domain`. Rule-8
  tables keep one positive and one negative row per rule. P-31: the tenancy `files` fixture keeps
  `[fake, garage]` only for tests that read or write files (the report lists the ~25 that do
  not: they get `fake` only). Forbidden in stage 2: the P-40/P-41 survivor functions
  (`test_a_stored_book_takes_no_other_state_through_any_replace`,
  `test_a_replace_that_changes_the_type_cannot_write_a_state`). Check per merged group: change the
  branch the group exercises by hand (one line, e.g. invert its condition), see the surviving case
  fail, revert; the commit body names the branch.

### Stage 3: dropped tests (class 3)

- **PD-11**: Drop P-40, P-41, P-43, P-45, P-49, P-50, P-51 as listed. P-42: first add the `2` /
  `2.0` spelling as a case of `test_migration_chain.py::test_a_fork_is_refused_naming_both_files`,
  then drop both tests. P-44: first add `@example` with the FLAT policy to
  `test_the_application_is_never_a_tenant_under_any_accepted_policy`, then drop the `[URIRef]`
  case. P-45: first confirm `scenario-map.csv` holds the integration test
  `test_a_disabled_service_account_is_refused_a_token_until_it_is_enabled` at `high` on "disable an
  account"; if not, keep the e2e test and record why. P-49 is dropped (its assert is a tautology;
  observing a private compile count is not worth an instrument). Each drop names its survivor in
  the commit body.

### Stage 4: broken rules (all but 11)

- **PD-12**: From the report's *Broken rules* tables, located by function name. A report row not
  named below is out of scope for this EPIC and is copied under *Debt* by task 4.6 (rule 10's
  other unseeded values, the other vacuous-assert rows, rule 9's "soft" rows among them).
  - **rule 21**: rename by feature: entrypoints `test_stage1_adversarial.py` → split into
    `test_one_label_adversarial.py`, `test_record_etag_adversarial.py`,
    `test_tenant_delete_adversarial.py`, `test_id_source_adversarial.py` by the feature each test
    names; `test_stage2_adversarial.py` → `test_tenant_write_validators_adversarial.py`;
    `test_stage4_adversarial.py` → `test_allowed_actions_adversarial.py`; generation
    `test_stage3_adversarial.py` → `test_typescript_service_types_adversarial.py`; testkit
    `test_stage1_adversarial.py` → `test_lazy_guard_names_adversarial.py`; services
    `test_iri_policy_stage2_adversarial.py` → `test_iri_policy_guard_adversarial.py` (narrow its
    `pytest.raises(Exception)`, drop the stale xfail comment); fix the "stage n" docstrings of
    the four collaboration adversarial files;
  - **rule 1**: `tests/unit/domain/test_tenant_move.py` moves to `tests/unit/services/`;
    `test_iri_policy_effective.py` builds its `ServiceSettings` locally instead of importing
    `tests.toy`; the testkit tests at the `tests/unit/` root (`test_testkit_bootstrap.py`,
    `test_testkit_lazy_import.py`, `test_container_selection.py`) move to `tests/unit/testkit/`;
    the services tests that drive the HTTP router move to `tests/unit/entrypoints/`;
    `test_token_verifier.py` moves to `tests/unit/adapters/`; `test_packaging.py`'s wheel test
    gets `@pytest.mark.slow`; `tests/perf/` stays (its own lane);
  - **rule 3**: `tests/unit/services/test_loading.py`'s tests that start an `HTTPServer` (rdflib
    fetches the remote JSON-LD context through `urllib`, which `httpx.MockTransport` cannot catch)
    move to a new `tests/integration/network/` (a local server is allowed there), with a
    `DirectoryMarkers("integration/network/", ("integration",))` row in `tests/conftest.py` so
    they start no container;
  - **rule 5**: each listed monkeypatch of toolkit code becomes the testkit fake where one exists
    (`FakeEventBus`, `FakeStore`, the relay's fake); where none exists it stays and is listed
    here under *Debt*;
  - **rule 6**: the one bare dict used as model data (`test_tenancy.py`, Scan slots) goes through
    the model;
  - **rule 7**: `rdf_persistence.testkit.roundtrip.assert_isomorphic` (exists) replaces
    `assert_same_graph` (`test_mapper.py`) and every raw `assert isomorphic(` in `tests/`; N-Quads
    string compares (`test_store.py`) become graph compares; substring checks on Turtle/JSON-LD
    text (`test_partial_import.py`, `test_conformance.py`) parse first;
  - **rule 9**: problem responses asserted by status and `type` where the table lists them;
  - **rule 10**: the `uuid4()` parameter values of `test_session_loaded_graphs.py` become fixed
    UUIDs;
  - **rule 12**: in-process timeouts take an injected clock or a fake sleep where the code under
    test accepts one; where it does not, the test stays as it is and is listed under *Debt*:
    the three `test_events_route.py` absence waits, `test_relay.py`'s d18 hanging publish and
    `test_tenant_dump.py`'s `created_at <= datetime.now(UTC)` (that one becomes
    `created_at <= ` a timestamp taken before the dump, which needs no clock);
    `test_router_hardening.py` drops its `asyncio.timeout(5)` and asserts the 413 only; the wall-clock asserts (`test_fakes.py` linear-time splitter, the store
    budget asserts of `test_session.py`, `test_transaction.py`, `test_unique_keys.py`) move to
    `tests/perf/` (the perf lane allows timing); `test_zitadel.py`'s polling loop uses
    `wait_until_async`; the testkit's `probe_timeout` test keeps its 0.01 s wait (the spec needs
    a real probe) and is recorded here as an accepted exception;
  - **rule 13**: `test_redis_events.py` restores `stream-node-max-entries`; `test_fuseki_smoke.py`
    uses a namespaced dataset name; the e2e `reader` disable stays (restored in `finally`);
  - **rule 14**: the `R4-1` skip becomes a removed parameter combination;
  - **rule 15**: each feature scenario names its spec scenario in a `# spec: <capability> /
    <scenario title>` comment above it; `iri_policy.feature`'s "live and die" scenario, which
    matches no spec scenario, gets `# spec: none` and is added to the report's spec questions;
    `tests/feature/example.feature` and `test_example.py` are deleted;
  - **rule 17**: `test_iri_policy_adversarial.py::test_the_settings_an_iris_was_built_from_cannot_change_what_it_mints`
    asserts the assignment is refused (`pytest.raises`) and the minted IRI unchanged; the
    migration-files brace test asserts load-or-refuse explicitly; the container
    `test_dependents_cost.py` measurement moves to `tests/perf/` with one assert (both variants
    complete and the drop variant's median is at most three times the other's); "does not raise"
    tests stay.

### Stage 5: rule 11

- **PD-13**: Every assert without a message gets one naming the idea it checks. A tuple assert
  (`assert (a, b) == (x, y)`) splits into one assert per element, conditions unchanged. Nothing
  else changes: Then-step guard asserts stay. The DEC-5 function is exempt.

### Map and report upkeep

- **PD-16**: `tests/audit/scenario-map.csv` is refreshed at the end of stages 2, 3 and 4 (rows
  of removed or renamed tests updated, merged cases need no change: rows are per function), by
  `tests/audit/refresh_map.py` (written by task 2.8, standard library only): it diffs
  `pytest --collect-only -qq` function ids against the map, drops rows of tests that are gone,
  and prints renamed or new ids for the lead to map by hand.

### Process

- **PD-14**: Review per P-0005: one L2+L3 pass per stage; the full review once after stage 5.
  The adversarial tester runs after task 1.2 (the one production signature change). Gates per
  `develop/agents.adoc`; each stage's PR carries the lead's `make check-all` and
  `make test-containers` results.
- **PD-15**: After stage 5, a closing PR (stage 6) re-runs the audit's run A, run B, the
  container runs and the domain mutation run, and adds `tests/audit/report-<date>-after.md`
  (before/after), then archives the change.

## Order dependence

None found. PD-9's `pytest-randomly==5.1.0` trial ran green on `--randomly-seed=1` and
`--randomly-seed=2` (7379 passed, 18 skipped each); the plugin is adopted in the `test` group.

## Debt

Filled during stage 4 (rule 5 items without a fake).
