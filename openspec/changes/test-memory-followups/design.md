> Derives from: the EPIC `test-memory-followups` (proposal.md, DEC-1 to DEC-7)

## Context

`inputs/seed.md` holds the four follow-ups and the code facts. The testkit's memory plugin
(`agent-test-control` PD-9) already clears `SchemaView`, FastAPI and `typing` caches after each
test; this EPIC removes the two causes in our own code and the test's order dependence.

## Goals / Non-Goals

**Goals:** a dropped kit is freed without clearing `typing`'s caches (DEC-1); one parse per schema
file per process for service kits (DEC-2); an order-independent parser-depth test (DEC-3); DEC-8
measured (DEC-4); the seed spike decided and its outcome landed (DEC-5); no test run nobody
reads, in this EPIC's own delivery (DEC-6); a shared file unchanged since the seed no longer forces
the fallback (DEC-7).

**Non-Goals:** the No-gos of the proposal.

## Decisions

- **PD-1 The dependency parameters** (DEC-1). In `Gate.tenant` and `Gate.aggregate`
  (`auth.py:86-101`) the inner `permitted` functions take `caller: VerifiedCaller =
  Depends(self.caller)`; in `sse.py:77-81` the three parameters take `= Depends(gate.caller)`,
  `= Depends(gate.tenant(Action.READ))` and `= Depends(link_to_context)`. FastAPI resolves the
  default-argument form exactly as the `Annotated` form; the OpenAPI document does not change
  (guarded by `tests/unit/api/test_openapi.py` and `tests/unit/api/test_openapi_served.py`).
  The testkit's `clear_caches()` gains a keyword-only `include_typing: bool = True` (named so
  after D-5; it shadowed the module as `typing`) (default unchanged, so
  callers see no difference) so a test can clear only the `SchemaView` and FastAPI caches; the
  docstring of `memory.py:_clear_typing` drops the claim that a kit's own dependency is the
  reason, and keeps clearing `typing` for other projects' code.
- **PD-2 The service view** (DEC-2). `service_view(path) -> SchemaView` in
  `rdf_persistence/schema/services/schema.py`:
  - **Key:** `(resolved path, st_size, sha256 of the root file's bytes)`. The content hash, not
    the modification time, decides: a rewrite within the clock's 1–10 ms step still gives a new
    key. Imported modules are not hashed (RISK-2).
  - **Store:** an `OrderedDict` used as an LRU of at most `SERVICE_VIEWS = 8` entries (a module
    constant), guarded by one `threading.Lock`. A hit moves the entry to the end; a miss calls
    `load_schema(path)` and evicts the oldest entry past the bound. At most one entry per resolved
    path: a new hash replaces the old entry.
  - **Release:** `clear_service_views()` empties the store. The testkit's `release_memory()` (the
    module-boundary step, not the per-test `clear_caches()`) calls it, so a test process holds at
    most the views of one module's schemas; its count joins the returned index as
    `service_views`.
  - **Errors:** the file is read before the lookup; on an `OSError` from that read,
    `service_view` calls `load_schema(path)` and lets it raise, so a missing or unreadable file
    raises exactly what `load_schema` raises today (type and message), tested against
    `load_schema`'s own error.
  - **Seam:** `service_view(path, *, load=load_schema)`; tests inject a counting loader.
  - **Scope of "once":** one parse per schema file until the next `release_memory()`, which in
    tests means once per module per worker; in a service, once per process.
  - **Use:** `ServiceKit.__init__` (`kit.py:166`) calls `service_view(schema)` instead of
    `load_schema(schema)`, so every kit built from a file shares its view, whether built by
    `install_service` or by constructing `ServiceKit` directly. `load_schema` and
    `generation_view` are untouched. `ServiceKit.view`'s docstring says the view is shared and
    must not be modified.
  - **Threads:** the lock covers lookup and load; loads of different files are serialised by it
    (accepted: a load is rare and one per schema per process). Concurrent reads of a shared view
    race only on `SchemaView`'s own lazy cache fills, which are idempotent, as they already are
    when one kit serves several threads today.
- **PD-3 The guard on modification.** A fingerprint of the view: `view.modifications` plus a
  sha256 over `yaml_dumper.dumps(module)` of every module in `view.schema_map`, in sorted key
  order (the root and every imported module `load_schema` placed there). A test takes it, builds
  a kit from the cached view, drives it through the toy service's scene covering create, read,
  list, replace, delete, a workflow transition, archive and restore of a tenant, the events route
  (one event decoded), and the start-up migrations, then asserts the fingerprint is unchanged.
  The same test also takes, before and after, a sha256 over `yaml_dumper.dumps(slot)` of every
  `class_induced_slots(c)` result for every class, without clearing the caches in between: the
  strings are computed at each point, so an edit made to a cached induced slot object changes the
  "after" digest even though the cache returns the same objects.
- **PD-4 The recursion pin** (DEC-3). A plain context manager `default_recursion_limit_pinned()`
  and an `autouse` function-scoped fixture `default_recursion_limit` that wraps it, both in
  `tests/unit/migrations/test_migration_files_adversarial.py`; the context manager sets
  `sys.setrecursionlimit(DEFAULT_RECURSION_LIMIT)` (`1000`, CPython's default, a module constant)
  before each test of the module and restores the previous limit in `finally`. The test that
  measurably depends on the limit is the 120-pattern step (under a raised limit it is not refused:
  task 1.3's planted check, D-3); the deeply nested YAML cases (`"{" * 5000`, `"[" * 100000`,
  `"[" * 50000`) passed under 20000 too, and the pin keeps them at the default as well. Nothing
  else in the module changes.
- **PD-5 The measurement** (DEC-4). From Langfuse, observations with
  `startTime` after #394's merge (2026-11-25 21:00 UTC), sessions whose root span's metadata
  `cwd` contains `rdf-persistence`, excluding this EPIC's own sessions. The window is the first
  epic session (one with `Subagent:` spans) during which at least two other rdf-persistence
  sessions have spans. Definitions:
  - **Gate command:** a `Tool: Bash` observation whose input `command` contains
    `make test-changed`, `make check-all`, `make test-fast` or `make check-quality`.
  - **Builder task gate:** the latency of each gate command under a `Subagent:` span whose
    command contains `make test-changed`; target: median < 3 min.
  - **`check-all` net time:** the latency of each `make check-all` command minus the `N` of its
    `test queue: waited Ns` lines in its output; target: < 15 min.
  - **Builder waiting share:** per `Subagent:` span, the sum of gate-command latencies, queue
    wait included, divided by the span's latency; target: < 10 % for every builder.

  `evidence/measure.md` holds one table: target, measured value, sessions and observation ids,
  met or missed.
- **PD-6 The seed spike** (DEC-5). Timebox: half a day; past it the spike counts as failed.
  - **Where:** a throwaway worktree off the stage branch; one small unit folder
    (`tests/unit/schema/`) and one small feature folder, never the full suite.
  - **The mechanism under test** (the one 2.2 would ship, so the spike runs it, not an
    approximation). Today the lanes differ from the seed: `test-unit` and `test-feature` use
    `LIBRARY_LANE` (no `tests/generator`) and random order; the seed uses `UNIT_LANE` and
    `-p no:randomly`; and `seed()` deletes the seed files before its command, so one `seed` call
    per lane would leave only the last lane's data. Hence: `test` runs its three lanes inside **one**
    `selection_data seed` call, under one queue hold:
    `TEST_QUEUE_LABEL=test $(SEED_RUN) python -m rdf_persistence.testkit.selection_data seed --
    env TEST_QUEUE=off RECORD_SELECTION=1 TESTMON_DATAFILE=.testmondata.seed $(MAKE) test-unit
    test-feature test-generator`. The inner lanes skip the queue (`TEST_QUEUE=off`; the outer call
    holds it) and, with `RECORD_SELECTION=1`, add `--testmon --testmon-forceselect -p no:randomly`
    to their pytest command; all three append to one `.testmondata.seed`, swapped once after the
    last lane, so the commit is recorded (PD-8). A failing lane makes `make` exit 2, which is no
    finished run: no swap, the earlier data stays. Under `CI` `test` is unchanged.
  - **Three runs**, on the two folders, each through the queue and the same worker count, each
    into its own data file named by `TESTMON_DATAFILE` with no swap: (a) coverage only, the lane
    commands as today (`make -n test-unit` / `test-feature` show them), into nothing; (b) selection
    only, the seed's pytest command, `TESTMON_DATAFILE=.testmondata.a`; (c) the mechanism above
    restricted to the two folders (`TEST_PATH` narrowed), `TESTMON_DATAFILE=.testmondata.b`, the
    two lanes appending in order.
  - **Pass**, all three: (1) the coverage report of (c) equals (a)'s line for line
    (`coverage report` totals and missed lines); (2) for three sample changes (one line in a
    `domain` module, one in a `services` module, one in a test file), `make test-changed` selects
    the same test ids with (b)'s data and with (c)'s data, each copied over `.testmondata` before
    its run (the copy is the swap, done by hand in the throwaway worktree); (3) (c)'s wall time is
    at most 15 % above (a)'s. Anything else, or a warning from either plugin about the tracer, is a
    fail. (c) runs in fixed order where (a) is random: criterion 1 compares coverage totals and
    missed lines, which order does not change.
  - **Pass → change:** the mechanism above, in `Makefile`'s `test` (local branch only); the
    lanes alone stay as they are. The docs say that a worktree where `make check-all` passed needs
    no seed for the next stage on that commit. Coverage floors are unchanged.
  - **Fail → record:** one paragraph in `develop/testing.adoc#test-control`: why the full run
    cannot double as the seed, with the run that showed it; nothing else changes.
  - `evidence/seed-spike.md` holds the three runs' commands, times, coverage totals, the selected
    test ids per sample change, and the verdict.
- **PD-7 No test run nobody reads** (DEC-6). How this EPIC's lead runs tests, and the check the
  stage report carries:
  - Seed (`make test-seed`) at stage start only because stage 1 has builders (tasks 1.1 to 1.3);
    the close (section 3) has none and seeds nothing.
  - One `make check-all` before the PR and one after the fix pass; never `make test-unit`,
    `test-feature` or `test-generator` by hand on top of it.
  - On a commit whose seed passed, the seed's result is the unit and feature pass/fail; a separate
    lane runs only when its coverage floor is the open question, and the report says so.
  - The stage report lists each full run with its reason (who reads its result); a run without one
    is a finding for the validation review.
- **PD-8 The seed's commit** (DEC-7). Two parts, both in the testkit:
  - **Recording**, in `rdf_persistence/testkit/selection_data.py`: `seed()` reads
    `git rev-parse --verify HEAD` before it runs the command, and records nothing when the tracked
    tree is dirty (`git status --porcelain --untracked-files=no` not empty; D-5, L5-W1: a dirty
    shared file later reverted to `HEAD` would otherwise be vouched for) (a commit made during the run then
    counts as a change since the seed: safe), calling git directly with
    `subprocess.run(..., cwd=root, capture_output=True, text=True, check=False)`, never through its
    `run` seam, which stays the pytest command's. Inside `swap`'s exclusive lock it deletes
    `.testmondata.commit` (constant `SEED_COMMIT`) **before** the rename, then, after it, writes the
    sha and a newline through a temporary file and `os.replace`; a crash between the two leaves new
    data with no commit file, which plans as today. When the sha could not be read (no git, no
    commit), nothing is written after the rename, so a commit file always describes the data
    beside it. A run that is not swapped (failed, interrupted) leaves both data and commit file as
    they were. `swap` gains a keyword `commit: str | None = None`; its CLI form (`swap <exit>`)
    passes none and therefore deletes the file (the `seed` subcommand is the path that records).
    `.gitignore`'s `.testmondata*` already covers the file.
  - **Reading**, in `rdf_persistence/testkit/changed_tests.py`: `seed_commit(root) -> str | None`
    reads the file and strips surrounding whitespace; anything but 40 or 64 lowercase hex
    characters (missing, unreadable, empty, garbage) gives `None`;
    `changed_since(commit) -> list[str]` is `changed_files`' listing against `commit` itself, not a
    merge base (committed and uncommitted differences, untracked files; `-z`, `--no-renames`), so
    a rebase that keeps the file's content keeps it unchanged. `main` takes the data check and
    `seed_commit` together under one shared `lock(root)` (today the check runs outside it), so the
    plan never pairs one seed's data with another's commit. The testmon run takes the shared lock
    again, as today; a seed swapping in between gives that run newer data than the plan read,
    which is the race of today, not one PD-8 adds. It computes `changed_since` only when the
    data check says `SOUND` and a commit is recorded; a `GitError` (the commit pruned) makes it
    `None` and adds the hint `cannot read the seed's commit <sha>: <git message>`.
  - **Use:** `plan(..., *, since_seed: Collection[str] | None = None)` and `select(..., *,
    since_seed=None)` (keyword-only, default the behaviour of today). With `since_seed` given, a
    path's own `fallback_reasons` from the classifier count only if the path is in `since_seed`;
    otherwise each becomes the hint `<path>: unchanged since the seed (<sha8>); its selection data
    covers it`. The classifier's `paths` and `hints` for that path, and the "folder does not
    exist" reasons, apply as today. `plan` passes `since_seed` only when `has_data`. One more
    rule: a path in `since_seed`, not in `changed` and **not testmon-visible**
    (`classifier.is_testmon_visible` is false, mirroring `_split`) is classified too, and only its
    `fallback_reasons` count, never its `paths` or `hints` (a shared file the branch changed,
    seeded, then reverted to the base's content: the data was recorded under a configuration the
    worktree no longer has). Testmon-visible files are left out, so a rebase that brings upstream
    Python changes (a `core` module) does not fall back: testmon judges those by fingerprint. A
    rebase that brings an upstream non-Python fallback path (a `Makefile` change) falls back until
    the next seed, correctly: the data predates that file. Today such a revert goes
    unnoticed; PD-8 closes it at no cost, since `since_seed` is computed anyway.
  - **Why it is sound:** the seed ran every unit and feature test with the file at the content it
    has now, so testmon's fingerprints describe a run under that configuration; what changed since
    is selected as usual. A `uv.lock` changed after the seed is in `since_seed`, so it falls back;
    the package check does not catch it on its own, since `test-changed` runs with `UV_NO_SYNC=1`
    and an unsynced lock leaves the installed packages as they were.
  - **API:** additive, semver minor: `SEED_COMMIT` joins `selection_data.__all__`;
    `swap(..., commit=None)` is a new keyword; `seed_commit` and `changed_since` join
    `changed_tests.__all__`; `select` and `plan` gain the keyword `since_seed`. The generated types
    do not change.

## Algorithm / approach

`service_view(path)`: read the root file's bytes (raises as `load_schema` would for a missing or
unreadable file); key = (resolved, size, sha256); under the lock: entry = store.get(resolved); if
the entry's key equals, move it to the end and return its view; else view = `load_schema(path)`,
store[resolved] = (key, view), evict the oldest past `SERVICE_VIEWS`, return view. Idempotent:
the same content returns the same object; retry-safe: a failed load stores nothing.

Worked examples (each a case of task 1.2's table):
- Two `ToyService()` built in one test: `kit_a.view is kit_b.view`.
- A test writes a schema to `tmp_path / "s.yaml"` and installs it: a new path, a new entry.
- The same path rewritten with other content, at once (no sleep, same mtime step): a new view.
- The same path rewritten with the same bytes: the same view.
- Nine different schema files: the store holds eight; the first is evicted and reloaded on use.
- `release_memory()` empties the store; the next kit loads again.
- A missing file: the same exception type and message as `load_schema(path)`.
- `generation_view(TOY_SCHEMA) is not service_view(TOY_SCHEMA)`.

`plan` with `since_seed` (PD-8; each a case of task 4.2's table, with this repository's
classifier and sound data unless stated):
- Branch changed `Makefile` before the seed; the task changes `rdf_persistence/api/x.py`:
  `since_seed = ["rdf_persistence/api/x.py"]` → one testmon run, no fallback, the hint
  `Makefile: unchanged since the seed (…)`.
- `Makefile` changed after the seed (`"Makefile"` in `since_seed`) → fallback, as today.
- An uncommitted edit to `pyproject.toml` → it is in `since_seed` (worktree diff) → fallback.
- `since_seed=None` (no commit file, a pruned commit, or data not sound) → today's plan exactly.
- `has_data=False` with `since_seed` given → `since_seed` ignored → today's plan.
- `docs/x.adoc` unchanged since the seed → still selects `tests/unit/tooling/test_check_docs.py`
  (only fallback reasons are set aside).
- `Makefile` changed on the branch, seeded, then reverted to the base's content:
  `changed = ["rdf_persistence/api/x.py"]`, `since_seed = ["Makefile", "rdf_persistence/api/x.py"]`
  → fallback (`Makefile`'s reason, from `since_seed`).
- After a rebase onto a newer base, `rdf_persistence/core/y.py` changed only upstream:
  `changed = ["rdf_persistence/api/x.py"]`, `since_seed = ["rdf_persistence/core/y.py",
  "rdf_persistence/api/x.py"]` → no fallback (`core/y.py` is testmon-visible, so it is left out).

The seed's commit (task 4.1's table, `seed()` with a fake `run` in a temporary git repository):
- A finished run on commit C → `.testmondata.commit` holds C.
- A run with failing tests (exit 1, a finished run as `FINISHED_RUN_EXITS` says) → swapped, the
  commit file holds C.
- A run that did not finish (exit 2, or 130) → not swapped: the old data and the old commit file
  stay.
- `root` not a git repository → the data is swapped, no `.testmondata.commit` is written.
- A stale `.testmondata.commit` beside a swap whose sha is unknown → gone afterwards.

### Anti-patterns
| Don't | Do instead | Why |
|---|---|---|
| Cache inside `load_schema` | `service_view` for kits only | `generation_view` modifies the views it loads |
| `Annotated[…, Depends(<per-kit callable>)]` | `= Depends(…)` default | `typing` caches the subscripted type and holds the kit |
| Quarantine the parser-depth test | pin the recursion limit for the module | the behaviour is right; only the environment varied |
| Key the store on the modification time | key on size and content hash | a rewrite within one clock step keeps its mtime |
| Modify `kit.view` in a test or a consumer | copy it (`deepcopy`) or load your own | the view is shared by every kit built from the file |
| Seed a worktree no builder will work in | skip the seed (P-0022) | only `make test-changed` reads it |
| Run `make test-unit` / `test-feature` beside `make check-all` | run `check-all` once | it already holds both lanes |
| Re-run a lane on a commit whose seed passed, for pass/fail | read the seed's result | the seed ran those tests; only the coverage floor is new |
| Adopt the combined run on a partial match | fail the spike (PD-6) | a wrong selection silently skips tests a change reaches |
| Diff every path against the seed's commit | set aside only fallback reasons (PD-8) | folder rules and testmon already judge the rest correctly against the base |
| Keep a commit file the swap did not write | delete it when the sha is unknown | a stale commit would vouch for data it does not describe |
| Read the seed's commit when the data is not sound | ignore it | the commit describes the data; unsound data cannot vouch for anything |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Code later modifies a shared view (a new feature) | PD-3's guard test fails | the feature copies the view or stops modifying it |
| An imported schema file changes while the importing file's bytes do not (same process) | not detected: the key hashes the root file only | accepted (RISK-2): tests write new files under new paths; a long-lived dev process reloads by restart |
| Two threads build kits from one file at once | the lock | one load, both get the same view |
| A suite installs services from many temporary schemas | the store's bound | at most eight views; `release_memory()` at each module boundary empties it |
| The schema file is missing or unreadable | the read before the lookup | the same exception and message as `load_schema`; nothing stored |
| Many threads read one shared view | n/a | lazy `lru_cache` fills race idempotently, as with one kit serving many threads today |
| The OpenAPI document changes with PD-1 | `test_openapi.py`, the served golden | stop; the default form must be identical |
| The pin leaks to later tests | the fixture restores the limit in `finally` | none |
| Langfuse lacks three concurrent sessions yet | PD-5's query finds fewer | measure later; the task stays open, the fixes merge |
| testmon and pytest-cov fight over the tracer | PD-6's pass criteria (coverage or selection differs, or a warning) | the spike fails; record it; no Makefile change |
| The combined run is much slower | PD-6 criterion 3 (> 15 %) | the spike fails |
| The spike overruns its half day | the lead's clock | counts as failed; record what was learned |
| A full run is started that nobody reads | PD-7's run list in the stage report | a finding for the validation review |
| The seed's commit was pruned (a rebase, then `git gc`) | `changed_since` raises `GitError` | a hint naming the sha; today's plan (the fallback applies) |
| The commit file is garbage or empty | `seed_commit` validates the hex | `None`; today's plan |
| A commit lands while the seed runs | the sha is read before the run | the commit's files count as changed since the seed: the safe side |
| The worktree was dirty when the seed ran | the sha is HEAD, not the dirty tree | the dirty files count as changed since the seed: the safe side |
| The seed swaps while a builder reads the commit file | the shared/exclusive worktree lock covers the read in `main` | the builder reads old data with the old commit, or new with new |
| A shared file changed back to its seed content | the diff against the commit is empty for it | set aside, correctly: the seed ran with that content |

## Risks / Trade-offs

- **RISK-1** (outside change: linkml/linkml#4284 fixed upstream; likely medium, impact low). A
  fixed `SchemaView` makes part of the testkit's clearing unnecessary. Accept: clearing stays
  harmless; revisit when the fix ships.
- **RISK-2** (who is hurt: a developer whose long-lived process edits an imported schema;
  likely low, impact low). The cached view would be stale. Accept: production loads once at start;
  tests use new paths.
- **RISK-3** (a smaller gain than possible). The testkit plugin clears `SchemaView` caches after
  each test, so a shared view recomputes its induced slots per test; before this change every test
  built a new view whose caches were cold anyway, so it cannot get slower, only gain less than an
  uncleared cache would. Check: task 1.2's timing (command and threshold there); more than 10 %
  slower than before goes to the developer.

- **RISK-4** (who is hurt: a builder whose change needs a test the selection misses; likely low,
  impact medium). A shared file that alters which tests exist (a new `testpaths`, a new marker
  filter) unchanged since the seed is set aside, correctly, but a later code change is selected by
  testmon only among the tests the seed saw. Mitigate: the hint names every file set aside, and
  `make check-all` before the PR runs every test; a new test file is still selected by its folder
  rule.

## Delivery decisions

- **D-1** (developer, 2026-11-26): the re-gate of the additions ended at 8.5 after two runs, with
  every gap of both runs folded in (`evidence/clarity-gate.md`); accepted, no third run. Named
  D-1, not DEC-8, because DEC-8 in this change means `agent-test-control`'s target.
- **D-2** (lead, 2026-11-26): each parallel builder and the spike work in their own worktree
  (`.worktrees/tmf-<task>` off the stage commit), not in the stage worktree, so one builder's
  half-done edit never reaches another's task gate; the lead commits each task onto the stage
  branch. No seed in those worktrees: `make test-changed` plans by folder rules there (P-0022's
  purpose, a cheap task gate, holds without seeding five worktrees serially in the queue).
  First sync was without `--all-extras` (lead's error, one builder gate lost); re-synced.
- **D-3** (lead, 2026-11-26, from task 1.3's planted check): PD-4's rationale corrected: only
  the 120-pattern step fails under a raised limit; the nested-YAML cases do not. The pin stands.
- **D-4** (lead, 2026-11-26, from task 4.2): the set-aside hint reads `<path>: unchanged since the
  seed; its selection data covers it`, without PD-8's `(<sha8>)`: `select` and `plan` see only
  `since_seed`, and widening the public API for a label is not worth it. The two lock tests that
  pinned "the data check runs outside the lock" now pin PD-8's shared lock around it.
- **D-5** (lead, 2026-11-26, the full review of the one stage; P-0005: an epic of one stage gets
  the full review, L1, L2, L3 apart and L4+L5 together, which also covers the stage's L2+L3 pass,
  so that pass is not run twice). No Critical. Accepted, one fix pass:
  - *Fixer (code):* L5-W1, a seed taken on a dirty tree records no commit (`git status
    --porcelain --untracked-files=no` not empty), so a dirty shared file reverted later can never
    be vouched for (PD-8 amended); L4-W2 and L3-S3, `clear_caches(*, include_typing=True)`
    instead of a `typing` flag that shadows the module (PD-1 amended); L4-W3, `set(changed)` built
    once; L4-W4 and L3-S5, `_since_seed` returns the paths only, `main` builds the hint; L2-W4, a
    test that fails if the autouse pin is dropped; L1-S1, `service_view` stores a view only if the
    file's bytes still hash to the key after the load; L2-S6, `service_view`'s docstring names
    RISK-2; L1-S3 and L5-S2, `changed_tests`' docstring names the window between the plan and the
    run (today's race, PD-8); L5-S3, the docstring rewrap.
  - *Lead (docs):* L2-W1, the memory bullet of `develop/testing.adoc`; L2-W2, the CHANGELOG
    entries for DEC-1 and DEC-2; L2-W3, the spike link to the change's current path (the archive
    moves it); L2-S5, the scan's result recorded in `evidence/timing.md`.
  - *Under the floor:* L3-W1, a store class instead of the module store (PD-2 decided a module
    function with one reset; no second consumer exists); L3-W2 and L1-S2, a read-only facade over
    the shared view (DEC-2 decided documentation plus PD-3's guard; `SchemaView` has no read-only
    form, a facade would re-wrap its whole API); L3-S4, `CacheCounts`' per-function keys; L2-S7,
    a test of the order inside `swap` (the end state is tested, the order is a two-line read);
    L5-S1, a per-path lock (loads are rare, PD-2 accepted the serialisation).

## Open Questions

None. Q1 to Q5 answered 2026-11-26 as recommended, plus DEC-7 (`inputs/qa.md` round 3); Q6 and
Q7 answered (DEC-5, DEC-6).
