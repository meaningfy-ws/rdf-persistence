# Memory investigation, 2026-11-25 (secondary, never groomed)

A subagent measured with serial runs (`-n 0 --no-cov -p no:randomly`, `/usr/bin/time -v`, a probe
plugin logging RSS per module and live objects); live figures from `ps`. Scripts and logs were kept
outside the repository.

| Run | Tests | Max RSS |
|---|---|---|
| import package and models, build `toy_mapper()` | 0 | 127 MB |
| collect-only, whole `test-fast` lane | 8730 collected | 446 MB |
| `tests/unit/persistence` (not slow) | 953 | 461 MB |
| `tests/feature` (not slow) | 99 | 1.97 GB, about 17 MB per test, rising steadily |
| `test_contract.py`, 10 cases | 10 | 516 MB, about 21 MB per case |
| 12 × `ToyService()` | – | 393 MB, about 20 MB each, all still alive |

Live: 26 pytest processes held 31.4 GB on a 62 GB machine with 22 GB of swap in use; one
session's contract-test workers at 3.5 to 4.6 GB each.

Culprits (measured):
1. linkml-runtime `SchemaView`: 73 unbounded `lru_cache(None)` caches on its methods, keyed per
   view, so every view and what it derives stays alive (about 5.4 MB each; 733 alive after the
   feature run). The tests call `load_schema(` 208 times, many at module level.
2. `fastapi.dependencies.models`: three `lru_cache(maxsize=4096)` caches keyed on endpoint and
   dependency functions, which close over the `ServiceKit`, keeping about the last 30 apps
   (about 0.6 GB) alive.
3. Each `ToyService` about 20 MB and 9 to 12 SchemaViews; function-scoped `service` fixtures.
4. `tests/unit/api/test_contract.py`: a schema per case; line 114 builds an app at import.
5. Module-level `load_schema`/`Documents` globals: about 310 MB per worker before the first test.

Second measurement (owner's input, 2026-11-25, another session's probe), one process,
`tests/unit/api/test_allowed_actions_adversarial.py`: each test builds a `ToyService()`
(`tests/unit/api/conftest.py:20`) whose `install_service` loads the schema into a new `SchemaView`
(`rdf_persistence/api/entrypoints/kit.py:184`); Python-tracked memory +19.5 MB per test, never
freed; process memory +35 MB per test (343 MB after test 1, 835 MB after test 12). Growth from test
5 to 12: about 70 MB in jsonasobj2 / linkml_runtime yamlutils / meta.py (the schema YAML parsed
again per test), about 13 MB in `copy.py` from `SchemaView.induced_slot` (cached copies), about
25 MB in `rdflib/plugins/stores/memory.py` (graphs not freed, probably the same cause). The span
recorder was ruled out. Production is not affected (one view at start-up). The consumer
application probably has the same leak (a test process at 9.7 GB). Its fixes: clear the
`SchemaView` caches after each test (stopgap); load each schema once per process and reuse the
view (proper, faster tests; a library or test-kit change); report upstream.

Probe of mechanism 1: clearing the SchemaView and FastAPI caches, `gc.collect()` and
`malloc_trim(0)` took 12 apps from 372 MB (12 kits alive) to 251 MB (none alive); releasing after
each app kept the process flat at about 200 MB. Worker recycling is unsafe under `--dist loadgroup`
(a worker exit counts as a crash; queued group tests are not rescheduled). `MALLOC_ARENA_MAX`: little
effect (live objects, not fragmentation).
