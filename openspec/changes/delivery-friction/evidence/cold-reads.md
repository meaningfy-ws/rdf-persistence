# Cold reads of howto/adopt.adoc, steps 4 to 7

Decisions: design.md PD-6a, PD-6b. Reader 1: 20 guesses, all fixed. Reader 2: 20 guesses; fixed B9, B17, C2, C3, C11, C18, 4, 5, 6, 7, 14, 15. Reader 3: see the end.

## Reader 1

Step 4
1. "`python` sets the Python folder when it is not the folder of `package`": value format (path relative to pyproject.toml?) and whether shapes/context/frames/openapi-components.json/rp-manifest.json move with it (page says they go "under library/domain/generated/"). Say what `python` moves.
2. "`openapi = false` leaves out openapi-components.json": step 12 says install_service raises OSError when that file is missing; say when false is safe (e.g. only when you don't call install_service).
3. "relative to the folder of the pyproject.toml": how is that file found (cwd only, search upward, --project flag)? Does rp-generate work from a subfolder?
4. "creates it, and its parent folders, and writes an __init__.py into it": do library/ and library/domain/ get __init__.py, or must I add them for imports to work?
5. "A missing schema file is an error": exit codes for missing schema file / broken rule, what success looks like. List exit codes 0, 1, 2.
6. regenerate-command example `make generate-models` vs TOML `"make generate"` vs target `generate`: use one name throughout.
7. "Your regenerate target writes ... one Python module per schema module": are files no longer produced (renamed/removed module) deleted? Does --check report them?

Step 5
8. "Each object, owned parts included, has an id": is id required when building a part (Chapter) in Python? The service mints part ids when a body omits them.
9. Book(id=..., label="Dune", description=...): label/description not in books.yaml; name the fields the mixins (Described, Tracked, AggregateRoot) add and which ones you never set (session sets tracking fields).
10. id="https://example.org/library/books/1": does the class check IRI shape, or only the session? Could this example object be stored?
11. "No BaseModel ... in domain, services or entrypoints": step 2 layout lists none of those folders; add them (library/domain, library/services, library/entrypoints?).

Step 6
12. pytest_plugins = ["rdf_persistence.testkit.freshness"]: how it finds [tool.rp-generate], what a stop looks like, whether it needs the `generate` extra.
13. CI and pre-commit `uv run rp-generate --check`: if CI runs pytest with the plugin, is the separate command needed? Pre-commit hook entry not shown. Say "CI: X; tests: Y; pre-commit: this hook".
14. assert_models_generated(ROOT / "library", roots=[...]): how first arg differs from roots; is this the step-2 file guard; why web/ isn't in roots.
15. allow=["library/domain/<file>.py:<ClassName>"]: relative to what?
16. conformance.run(SCHEMA, ...) / Conformance.of(SCHEMA): how they find generated classes and shapes; what the returned list holds.
17. constraint kinds list: which schema construct maps to which kind (minimum_value -> value_bounds?). Table or link.
18. round_trip(model, data.draw(aggregate(model, "Book")), "Book"): what it checks, what failure looks like.

Step 7
19. Upgrading rdf-persistence: the upgrade command for a git-pinned dependency (uv lock --upgrade-package rdf-persistence?); do --check and the plugin fail after an upgrade until regenerated?
20. Removing/renaming a module: must old generated files be deleted by hand? (same as 7)

Reader flagged as possible contradictions: 2 (openapi=false vs OSError) and 14 (web/ not in roots).

## Reader 2

To FIX (lead's selection):
B9  (step 6, blocking) "imports that entry's package, so it must be importable in your tests": step 1's pyproject.toml has no [build-system] / pytest pythonpath, and library/ has no __init__.py. How does library.domain.generated become importable? Show the required config (verify with a trial: a fresh project laid out as the page says).
B17 (step 7, blocking) Nothing on data already stored under the old model (added required slot, renamed slot, removed class). Will existing aggregates still read? Restart needed? State only what the code does today (find it: is there any migration? what happens when a stored graph misses a now-required slot on read?). Do NOT invent a migration procedure; if the toolkit has none, say so plainly in 1-3 sentences and say a restart is needed for the service to serve the new model (step 12).
C2  (step 2 vs 4) "Generated files go only in folders named generated" vs diagrams = "docs/model": exempt or not? Make consistent with what the guard actually does.
C3  (step 2 vs 6) guard lists differ (shapes, contexts, schemas, TypeScript vs shapes, contexts, frames, JSON schemas, OpenAPI, .ts). Use the true list (guards.py) in both.
C11 (step 6) "instance files, which live beside the cases file" vs instances/chapter-ok.yaml: say paths are relative to the cases file (verify).
C18 (step 7 vs 4) "you delete nothing by hand" vs edited file kept: add "unless it was edited (step 4)".
4   (step 4) add a closing line: run your regenerate target; expect the message.
5   (step 4) --check: success output + exit 0, and what it reports before the first generation (no manifest) — verify.
6   (step 5) kit.iris.mint_aggregate before any kit exists: point to the step-14 "outside a service" Iris(...) snippet or say the kit comes in step 12.
7   (step 5) guard scans library/domain but skips generated/: say "outside generated" (verify).
14  (step 6) "add a folder that holds none" → "you may add any folder that holds no hand-written .ts files".
15  (step 6) say CI needs the generate extra for --check (verify extra name).

NOT fixed (minor, recorded only, PD-6b):
1  (step 4) what a "target" is in "generated 1 target(s)".
8  (step 5) the part-template sentence uses step-14 terms without a link.
10 (step 6) `rp_generate_projects`: which "other files", and its TOML form.
12 (step 6) whether constraint kinds inherited from the metamodel mixins count as used.
13 (step 6) `book-ok.yaml` not shown in full.
16 (step 6) the pre-commit `files:` pattern misses `uv.lock` and `pyproject.toml`.
19 (step 7) follow-ups after removing a module: root `imports:`, conformance cases.
20 (step 7) what to commit together after an upgrade.

## Reader 3 (blocking and contradictions only)

Blocking 0, contradictions 2, both fixed by the lead: steps 1 and 4 said every run without the
`generate` extra exits 2, step 6 that `--check` then compares the manifest only (now both say so);
step 2 said the file guard looks "anywhere", step 6 only in its `roots` (step 2 now points to step 6).

## Reader 4 (blocking and contradictions only) — passes PD-6b

Blocking 0, contradictions 0. Near-misses: (1) step 4 "Run it: it prints the message above" was
ambiguous — fixed by quoting the line; recorded, not fixed: (2) step 5's list of rules the classes
enforce omits cardinality and value bounds, which step 6's cases expect both the class and the
shape to fail; (3) which constraint kinds the metamodel mixins bring (`identifier` from
`Described`); (4) whether `rp_generate_projects` replaces or adds to the rootdir `pyproject.toml`,
and its TOML form.
