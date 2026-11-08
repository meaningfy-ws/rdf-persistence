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
