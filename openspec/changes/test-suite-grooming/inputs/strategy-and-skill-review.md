# Testing strategy and the test-suite-care skill: review (draft)

Draft for the lead; the owner reads the final. Sources: the audit `tests/audit/report-2026-11-16.md`
("report"), `tests/audit/scenario-map.csv` ("map"), `tests/audit/slow-markers.md`, the PLAN
`openspec/changes/test-suite-grooming/{proposal,design,tasks}.md`, the session trace
`temp/audit/session-trace.md` ("trace §n"), the findings `temp/audit/map/*.findings.md`, and the
skill under `meaningfy-building/3.19.0/skills/test-suite-care/`.

## Part 1. Testing strategy for this repository

### 1.1 Practices: keep, change, drop, add

| Practice | Verdict | Evidence |
|---|---|---|
| Tiers (unit, feature, integration, e2e, perf) and make lanes (`test`, `test-fast`, `test-changed`, `test-containers`, `test-perf`) | **keep; change** perf | The tiers fit: 3,396 unit functions, 43 feature, 184 container (report, *Numbers*). But `test-perf` is in neither `check-all` nor CI (`.github/workflows/ci.yaml` runs `test-unit` and `test-feature` only), and the audit never ran it (report, *Not measured*). Stage 4 moves every wall-clock assert into `tests/perf/` (design PD-12, rule 12), so the lane must run somewhere: add it to the lead's full gates beside `test-containers`. |
| Markers by path (`DirectoryMarkers` in `tests/conftest.py`), no per-file `pytestmark` | **keep** | Makes the tier a fact of the folder. Rule 1 misplacements (testkit tests at `tests/unit/` root, router tests under `unit/services/`) are the only cost (report, *Rule 1*); stage 4 moves them. |
| Coverage floors (80 % `make test`, 50 % features, 0 % containers) | **keep as a net, not as a measure** | 95.6 % line coverage, yet mutation of `domain/` still found 35 logic survivors and one function (`Iris.part_needs_type`) with no domain test (report, *Mutation run*). The floor catches untested files; it says nothing about whether tests bite. |
| Per-test coverage contexts (run B) | **audit only** | 231 s and a 215 MB data file (trace §8.2); worth it once per audit, not per change. |
| BDD features | **keep; change** | Small and cheap (48 cases, 17 s). 28 feature tests do not name their spec scenario (rule 15), and `example.feature` is a scaffold leftover (report, *Rule 15*). Features are where scenario traceability is cheapest; keep them few and named after the spec. |
| Adversarial files per stage | **change** | 983 of 3,623 functions (27 %, map), four of the ten costliest files, and most class 2 waste (P-27 to P-29, about 210 cases). 6 files are named by stage (rule 21). 982 of 983 are named by no commit or document, so nobody can tell a test that pins a fixed defect from a probe (report, *W-7*). Keep the tester; change what it leaves behind (rules 5 and 6 below). |
| Hypothesis | **keep; change** | 62 `@given` in 14 files. The CI profile is loaded at import of one test module, so only some xdist workers derandomise (trace §8.1); PD-9 moves it to `tests/conftest.py`. Use it more: many class 2 value lists (P-22, P-23, P-30) are hand-picked samples of one class that a property states better. |
| Fakes over mocks | **keep** | The testkit fakes are why the unit tier is fast and mutation-strong. About 10 monkeypatches of our own code remain (report, *Rule 5*). |
| Golden files | **keep** | Regenerated only by a make target, Turtle compared by meaning (`develop/testing.adoc` rule 7). The library review found no need for snapshot libraries (report, *Libraries*). One open question: which spec requirement the "equals the committed tree" tests serve (report, *rp-generation*). |
| Container tests | **keep; change** | 56 of 61 W-5 candidates were kept because they run the real store (trace §8.13). Waste found: the tenancy `files=[fake, garage]` axis runs about 25 tests twice for nothing (P-31), one e2e test repeats an integration test (P-45), wall-time asserts (rule 12), and two data leaks (rule 13). Not in CI by decision; they stay a lead gate. |
| `test-changed` lane (`tests/changed.py`) | **keep** | Does what pytest-testmon would; the library review rejected testmon (report, *Libraries*). |
| Mutation testing (mutmut, `make mutation`) | **add, on demand, per layer** | `domain/` in 56 s with its own tests, 89.8 % killed, about 92 % without message-only mutants (report). It is the only measure of whether tests bite, and the evidence a drop needs (report, *what this means for reduction*). Not in `check-all`. |
| Timeouts (pytest-timeout, CI `timeout-minutes`) | **add** | CI had no job timeout, and the async relay and event tests can hang (trace §8.1; PD-9). |
| Quarantine marker | **add** | One flaky test seen once and never identified (trace §6); one `pytest.skip("R4-1")` with no issue (rule 14). |
| `slow` marker and `test-fast` | **keep; fix** | 27 markers were wrong: 18 tests of 2 s or more alone had none, 9 marked tests ran under 0.5 s (`tests/audit/slow-markers.md`). Re-time after any fixture change (PD-6). |
| `--dist worksteal` | **trial** | Long `slow` tests idle workers at the end of a run (P-7). |
| pytest-randomly | **trial once** | Not installed, yet the Makefile disables it (report, *Libraries*); the trial decides. |
| polyfactory | **drop** | No test uses it; 399 calls to validated named builders in `tests/toy.py` meet the rule's intent. The real smell is 101 `model_copy(update=…)` that skip validation (report; DEC-4). |
| The scenario map | **keep; refresh per stage** | It is what made class 3 safe: every drop names a `high` survivor on the same scenario. Refreshed by `tests/audit/refresh_map.py` (PD-16). Its weakness: 72 % of rows sit at requirement level (2,606 of 3,623), only 14 % at scenario level (map). |

### 1.2 How tests should be designed here

1. **One test per scenario behaviour, at the lowest tier that runs it for real.** A higher-tier
   copy is kept only when it runs something real the lower one fakes. *Finding:* P-45 (e2e repeats
   the Zitadel integration test while booting three containers); the 56 container tests kept
   because they read the real store (trace §8.13).
2. **Parametrise across equivalence classes, not within one.** One case per class, plus the
   boundaries; a rule table keeps one positive and one negative row per rule (rule 8). *Finding:*
   about 756 cases in P-20 to P-34, mostly status codes, hostile strings and paths that hit one
   branch (e.g. Fuseki "any other status": 30 cases, one branch, misc §3).
3. **A value list longer than three in one class is a property.** Write a Hypothesis property with
   `@example` for the boundaries. *Finding:* P-22, P-23, P-30 (IRI-policy and SPARQL value lists).
4. **Every parameter axis must change the outcome.** An axis that the test never asserts on is
   removed, not kept "for coverage". *Finding:* P-31 (`files=[fake, garage]` on tests that touch no
   file; 16 `test_documents.py` functions run under two IRI policies that play no part).
5. **An adversarial test names what it guards.** Its docstring says either "found defect
   `<commit or finding id>`" or "probe of `<PD-/RISK- id>`". The file is named by the feature it
   attacks. *Finding:* W-7 undecidable for 982 of 983 tests; 6 stage-named files (report, *W-7*,
   *Rule 21*).
6. **The stage's adversarial tests are distilled before the PR.** Probes that pass on first run
   and share a branch collapse into one parametrised case per class (rule 2 above); only failing
   probes and decision guards stay as separate tests. *Finding:* the three collaboration
   adversarial files hold 332, 177 and 172 cases (report, *Where the time goes*), with P-27 to
   P-29 removing about 210.
7. **A fixture shares what no test changes, and rebuilds only what tests change.** Costly,
   read-only things (a schema view, a generated tree, a key) are session-scoped templates or
   process caches; stores and mocks stay per test. *Finding:* `service`, `bootstrapped`, `shelf`,
   `books`, `signer` (P-1 to P-5); half of the unit time was set-up (0.46 share).
8. **Our own ports are tested through their fakes, never by patching our own code.** Fakes take
   failure injection. *Finding:* rule 5 rows (`test_receive.py`, `test_events_route.py`,
   `test_migrate_dataset.py`).
9. **Every assert checks a value, with a message; "does not raise" is not a test.** *Finding:*
   about 1,120 asserts without a message; a tautology `x is x` (P-49); a test that returns before
   its assert (rule 17); about 30 "does not raise" tests.
10. **No wall clock outside `tests/perf/`.** Absence is proved after a deterministic point,
    not by waiting out a timeout; time is injected. *Finding:* rule 12 rows (0.2–0.3 s waits in
    `test_events_route.py`, `perf_counter` budgets in container tests).
11. **Every new test cites its spec scenario** (feature title, or docstring with capability and
    scenario). This is what makes the map cheap and `high`. *Finding:* `high` needs two of name,
    covered code, spec id; most evidence came from docstring ids (BRIEF; map evidence column).
12. **Before dropping a test of a strong layer, check mutants, not lines.** *Finding:* W-4
    containment was refuted on reading in 11 of 12 generation pairs and 0 of 431 entrypoint pairs
    held (trace §8.7, §8.11); domain tests kill about 92 % of meaningful mutants (report).

## Part 2. The test-suite-care skill

### 2.1 What worked

- **Measure first, class 1 first.** Run A showed set-up at 0.46 of unit time; the six costliest
  fixtures gave P-1 to P-5 with no test removed (report, *Proposals*). This is the skill's core
  claim and it held.
- **The two scripts and commands ran verbatim** through the project's own `make test` with
  `PYTEST_ADDOPTS` (trace §8.2).
- **"Contained is a hint, never proof"** was right: reading refuted most W-4 candidates
  (trace §8.7, §8.8 "W-4 almost always refuted on reading").
- **The map caught a spec contradiction** (rp-messages empty commit, trace §8.11) and about 45
  spec questions: value beyond waste.
- **One shared brief for nine mapping agents** produced 3,439 rows with no duplicate or missing
  row (trace §8.3, §8.11); per-chunk inputs (covered files, overlap extracts) kept each agent
  within about 9 minutes.
- **The survivor rule and "real store is never W-5"** stopped three wrong drops (P-46 to P-48)
  when the lead applied them (trace §8.13).

### 2.2 What failed or misled

In short (details and evidence in 2.3): the measuring step misled twice (xdist-inflated timings,
fixture rows mixed into the phase file); two signals over-report (`no_lines` 905 cases, W-7 true
for 982 of 983 tests); W-4 cost the most reading for 5 proposals; W-5's guard was broken by an
agent that read only `waste.md`; W-8 has no workable method; the tier list missed `tests/perf`;
the skill has no path for a waived sample; and the report template let "X or Y" fixes reach the
PLAN, where the clarity gate scored 7.0.

### 2.3 Improvements (numbered; file, change, motivation)

1. **`references/measuring.md`: add a confirm-alone step for W-2.** Candidates from run A are
   re-run alone (`-p no:xdist`, idle machine) before any marker proposal; report only confirmed
   ones. *Trace §8.11: 14 of 32 false.*
2. **`scripts/phase_times.py`: separate phase and fixture rows.** Write fixture rows to
   `<out>.fixtures` (or tag every row with `kind`) in every mode, not only under xdist; document it
   in `measuring.md`. *Trace §8.11 crash.*
3. **`scripts/overlap.py`: classify `no_lines`.** Read the coverage `source` and `omit`, and split
   `no_lines` into "calls code outside the source" and "candidate W-6". *Trace §8.2: 905 cases.*
4. **`scripts/`: add `covered_files.py`** (per test function, the package files its call covered,
   from the run B contexts) and a timing summariser (tiers, files, fixtures, slow candidates).
   `scenario-map.md` names the first as the map's input. *Trace §8.2: both written by hand,
   both generic.*
5. **`references/waste.md`, W-4: narrow before reading.** Read only `contained` pairs that the map
   already puts at `high` on the same scenario, and say the expected yield is low; prefer W-8
   evidence for strong layers. *Trace §8.7 (11 of 12 refuted), §8.11 (0 of 431).*
6. **`references/waste.md`, W-5 row: repeat the guard in the evidence cell.** "A test whose
   outcome is read from the real store, adapter or service is never W-5." *Trace §8.13: P-46 to
   P-48.*
7. **`references/waste.md`, W-7: change the evidence.** Replace "no fix commit names the test"
   with "no commit that touched both the test and production code, and no docstring marker
   `found defect`"; until the marker exists, W-7 needs W-8 evidence. *Trace §8.6; report, W-7.*
8. **`references/waste.md`, W-8: give the method.** (a) Run mutation per layer with that layer's
   tests first; widen only for survivors. (b) Discount mutants that change only an exception
   message (rule 9 forbids asserting it). (c) For a drop, use a targeted pair: mutate the code the
   dropped test covers, run the survivor alone, and require it to kill every mutant the dropped
   test kills. (d) Expect mutmut's stats phase to be serial and dominant, and its baseline to fail
   on parametrised ids with control characters; the fallback is per-layer results only.
   (e) Copy non-source files the tests read (`also_copy`). *Trace §8.4, §8.12, §8.13.*
9. **`SKILL.md` Workflow step 1: tiers from lanes.** List the tiers from the project's make
   targets (and CI), not its folders; a lane that no target runs is reported under *Not
   measured*. *Trace §8.13: perf.*
10. **`SKILL.md` Rules and `scenario-map.md`: the waived sample.** If the owner waives the sample
    check, record it in the report's header and *Decisions*; class 3 may then go only with
    W-8 (pair) evidence or a named `high` survivor re-read by the lead. *Trace §9.*
11. **`assets/report-template.md`: one decided fix per broken-rule row.** The *Broken rules*
    table gets a "Fix (one, decided)" column; an open choice goes to *Spec questions* or a
    "Owner choice" column, never into the fix. Also add the sections every real audit needed:
    *Held back*, *Spec questions*, *Libraries*, *Mutation run*. *Trace §9: clarity gate 7.0.*
12. **`SKILL.md` Workflow step 2: fan-out guidance.** One shared brief file for every mapping
    agent; the lead prepares per-chunk inputs (covered files, overlap extract); chunks of 300 to
    500 functions; agents are read-only and write only their CSV and findings; the lead merges and
    checks the count. *Trace §8.3, §8.11.*
13. **`references/scenario-map.md`: partial scenario coverage.** Add a field (e.g. `part`: the
    scenario a lower-tier test serves in part) so "scenarios with no test" merges tiers before it
    reports. *Trace §8.6, §8.11: 76 over-reported gaps.*
14. **`references/measuring.md`: xdist fixture note.** Under `--dist load` a session or module
    fixture is built once per worker; savings from widening a scope are per worker. *Trace §8.5.*
15. **`scripts/overlap.py`: report exact group sizes for `identical_cases`** so class 2 counts are
    not estimates. *Report, P-20 to P-34 "~" counts.*

### 2.4 What belongs to other skills

| Skill and file | Change | Motivation |
|---|---|---|
| `cosmic-python` `references/testing-checklist.md`, rule 6 | Accept validated named builders as meeting the rule; name `model_copy(update=…)` (skips validation) as the smell; polyfactory becomes an option, not a mandate | Report, *Libraries*; trace §8.1; DEC-4 |
| `cosmic-python` testing checklist | A test that reads docs or repo files outside the package couples the suite to them; say so | Trace §8.13 (mutation copy lacked `docs/`) |
| `epic-delivery` `references/team-and-briefs.md`, Adversarial tester | Each test's docstring records "found defect `<id>`" or "probe of `<id>`"; the tester distils passing probes into parametrised classes before step 4 | Trace §8.7; report, W-7 |
| `project-setup` | The scaffold's `example.feature` should be flagged by a layout check once real features exist | Trace §8.10 |
| `epic-planning` / `clarity-gate` | A PLAN derived from an audit must decide each "or" before scoring | Trace §9 |

## Part 3. Before and after

From `tests/audit/report-2026-11-17-after.md` (the full table and the commands are there).

| Measure | Before (2026-11-16) | After (2026-11-17) |
|---|---|---|
| Unit + feature cases | 7,357 passed, 18 skipped | 6,790 passed, 0 skipped |
| `make test` wall (with coverage) | ≈ 214 s | 127 s |
| Run A wall / set-up share | 123 s / 0.46 | 72 s / 0.42 |
| `make check-all` | 3 min 59 s | 2 min 28 s |
| Container tier | 267 passed, 311 s | 257 passed, 297 s |
| Wrong `slow` markers | 27 | 0 at the thresholds |
| Mutation of `domain/` | 974 of 1,085 killed | the identical surviving set |
| Coverage | 95.6 % | 95.6 % |
| Asserts without a message (rule 11) | 1,301 | 0 |

The suite is about 8 % smaller and 41 % faster, with the same coverage and the same mutation
result: the shape the skill promises (cost removed, effectiveness kept) held, but only because
measurement overruled three estimates and review overruled four merges.
