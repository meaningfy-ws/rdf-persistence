<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: test profiling

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> *Detailed test profiling.* The check timings are rough; a profile of the slowest tests would show
> where the 5 minutes of unit and feature tests go.

From `docs/modules/ROOT/pages/develop/index.adoc`, "How long the checks take":

> These are rough wall-clock times from ordinary runs on a developer laptop, not from profiling.
> Use them to plan, and add a row or update one when a run differs a lot. Detailed profiling
> comes later.

## Open questions for the developer

1. **Which targets are profiled?**
   - (a) `make test` only: the seed's "5 minutes of unit and feature tests"; cheapest.
   - (b) `make test` and `make test-containers`: covers container start-up, which dominates the
     container lane; needs Docker for the measurement.
   - (c) every row of the table, including `check-quality` steps (mypy, freshness, docs): complete,
     but the static checks are already about 1 s to 10 s each, so little is learned.
2. **How is the profile produced?**
   - (a) pytest's built-in `--durations=N`, documented as a command: no new dependency, test-level
     only.
   - (b) a new `make profile-tests` target wrapping (a): repeatable by name, one more target to keep.
   - (c) a profiler (`pyinstrument`, `cProfile`) over the session: shows time inside fixtures and
     collection, adds a dev dependency and noisier output.
3. **With or without coverage?** Coverage slows every test. (a) profile as `make test` runs (with
   `--cov`): matches what developers wait for. (b) without: shows the tests' own cost. (c) both
   columns: most informative, a wider table.
4. **Where is it measured?** (a) a developer laptop, as today: what developers feel. (b) the CI
   runner (`ubuntu-latest`): reproducible machine class, readable from the job log. (c) both.
5. **How many slow tests are named?** For example the top 10, or every test above a threshold
   (say 1 s). A fixed number is stable; a threshold shows how long the tail is.
6. **Does collection and fixture set-up count separately?** The freshness plugin and
   `rp-generate` fixtures may cost more than test bodies. Splitting set-up from call time
   (`--durations` reports both) changes what the table must show.

## Test scenarios the EPIC must prove

- Running the documented command on `develop` prints the slowest tests with their times.
- The timings table rows for `make check-all` and `make test-containers` carry a measured time, a
  date and a commit.
- The table names the slowest tests or steps, and their share of the total.
- `make check-docs` still passes after the table changes.
