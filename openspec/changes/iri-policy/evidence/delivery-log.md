# Delivery log — iri-policy

Wall time and tokens per step, from ordinary runs (developer's request, 2026-11-08), so the
delivery loop can be made leaner. Agent figures are what the harness reports at completion; gate
times are `time make check-all`. The lead's own tokens are not reported by the harness: they are
left blank. Times are under load (other sessions ran `make` on the same machine).

## Steps

| Step | Who | Wall | Tokens | Tool calls | Notes |
|---|---|---|---|---|---|
| 2.1 gate | lead | 8m19s | — | — | 2886 tests |
| 3.1 build | builder | 20m05s | 111.5k | 32 | its own check-all 13m55s (835s) |
| 3.1 gate | lead | 6m24s | — | — | 2892 tests; review + 1 gap (PD-10a) recorded |
| 3.2 build (1st) | builder | — | — | — | stopped at the usage limit, nothing kept |
| 3.2 build | builder | 17m21s | 171.3k | 36 | its own check-all 12m18s |
| 3.2 gate | lead | 6m38s | — | — | 2956 tests; 1 gap (PD-7b) recorded |
| 3.3 build | builder | 42m48s | 214.1k | 85 | one early check-all (~11 min, 10 wording failures) before the lean rule reached it; then touched tests 28s + check-quality 49s |
| 3.3 gate | lead | 12m34s | — | — | 3042 tests (pytest 11m11s, load avg ~3–4 from other sessions) |
| 3.4 build | builder | 6m52s | 124.4k | 26 | lean brief + lean gates: touched tests 5.7s, check-quality 22s |
| 3.4 gate | lead | 8m41s | — | — | 3058 tests (load avg ~3.6) |
| 4.1 build | builder | 27m25s | 152.4k | 46 | e2e under containers (one full container lane 2m32s by mistake); found 2 stale integration tests from 3.3 (the lean gates do not run containers) and missing exports (PD-3d); used a bare `git stash` despite the rule |
| 4.1 gate | lead | 13m53s + 4m34s | — | — | check-all 3136 passed, 3 failed = tester files caught mid-write (re-run: 137 passed, 3 xfail); containers 172 passed |
| review L1 | reviewer | 4m08s | 103.5k | 16 | 1 major (reserved words at match time), 2 minor, 1 nit |
| review L2 | reviewer | 4m55s | 145.1k | 22 | 2 major, 4 minor, 2 nits |
| review L3 | reviewer | 3m09s | 96.1k | 17 | 1 major (access template split), 2 minor, 1 nit |
| review L4 | reviewer | 2m25s | 85.0k | 11 | 3 major, 6 minor, 5 nits |
| review L5 | reviewer | 2m32s | 96.7k | 13 | 2 major, 6 minor, 4 nits |
| adversarial tester | tester | 6m21s | 151.2k | 30 | 140 tests, 3 strict xfails |
| decide | lead | — | — | — | PD-12a–m recorded; 3 rejected with reasons. L2/L3 found the same major independently |
| fix PD-12a–m | fixer | 25m43s | 225.0k | 80 | 13 decisions; 1 divergence (access-record grant) caught; gates 1866 tests 250s + check-quality 36s |
| fix gate | lead | 10m41s + 2m49s | — | — | 3229 passed, 5 failed: the model guard refused `Iris` as a dataclass (PD-12i, the lead's decision missed a project rule); fixed inline in minutes; containers passed |
| gitnexus re-index | lead | ~3 tries | — | — | incremental and `--force` fail (gitnexus bug); `clean --force` + `analyze` works |

## Where the time goes (first reading, after 3.2)

1. **The full suite runs twice per task.** Builder `check-all` (12–14 min under load) then the
   lead's (6–8 min): about 60% of a task's wall time is gates, most of it the same tests twice.
2. **The suite is serial.** ~2950 tests in 340–660 s with one process; no `pytest-xdist`.
3. **Builders read a lot of design.** 110–170k tokens per task, much of it reading `design.md`,
   the spec and surrounding code to orient.
4. **Tool failures cost retries.** gitnexus re-index (3 tries), an earlier CI 429 and 504s.

## Aligned to the lean loop (from task 3.3, 2026-11-08)

The first tasks ran the older loop's habits. From task 3.3 on, per `epic-delivery`:
- impact once per stage (Prepare), not per task;
- the builder runs only its touched tests and `check-quality`; the lead runs `check-all` once;
- briefs in the template's short form, pointing at decisions instead of restating them.
Kept, because the LARGE appetite asks for them: five lenses, the adversarial tester, one checker per
stage, a cold reader on `adopt.adoc`.

## Candidates (to weigh, not yet decided)

- Builder runs only the tests of the files it touched plus `make check-quality`; the lead runs
  `check-all` once. Keeps the lead's re-run (the method keeps it on purpose) and drops the
  duplicate.
- `pytest-xdist` (`-n auto`) for `make test`: likely 3–5× faster; needs the order-dependent and
  timing tests checked (the known flaky listing and performance tests).
- Shorter briefs that quote the decisions they need, so a builder reads less.
- `gitnexus clean --force && analyze` as the documented re-index.
- Stop a builder once its task is committed. A builder that left a background wait loop running
  woke up hours later (3.1: 115k tokens, wall clock 3h12m including the idle time) and ran edit
  scripts on the shared checkout while the 3.3 builder was working there. Briefs should also say
  "no background wait loops: run gates in the foreground".
