# Handover (2026-11-19)

## Gates on the branch

| Gate | Result |
|---|---|
| `make check-quality` (with `check-docs`: links, anchors, fresh reference) | pass |
| `make test-generator` (with the tutorial's test) | 956 passed |
| `make test-changed` | 7873 passed, 3 failed: all three local only, see below |
| `make check-diagrams` | pass (the metamodel diagrams included) |
| `make build-docs` | built; 2 warnings, present on develop already (below) |

## Found, not fixed (out of this change's scope)

1. **CLI help names the wrong key.** `rp-generate --help` says `--schema` "overrides the
   `schema_file` key"; the key is `schema`. `build_parser` in `rdf_persistence_generation/cli.py`
   prints the field name. The generated reference shows the wrong text until it is fixed.
2. **Consumer terms in `user-manual/iri-policy.adoc`**: its example base and templates come from
   the first consumer's policy, as do `tests/e2e/test_library_policy.py` and `CONSUMER_POLICY` in
   `tests/toy_service.py`. Make the policy generic in tests and docs together.
3. **Unverified claim** in `user-manual/store-and-read.adoc`: "`kit.session` calls
   `open_session`"; the code goes through `tenancy.tenant_session`.
4. **Antora warning, older than this branch**: `architecture/generation.adoc` lines 332 and 339
   report "id assigned to anchor already in use: tool.rp-generate". The prose spans are now
   literal (`` `+[[tool.rp-generate]]+` ``) and the warning stays; its cause is not found yet.
5. **The `rp-generate` usage partial depends on the Python version's argparse layout** (3.13
   here). If CI runs another minor version, `make check-docs` reports it stale; regenerate it
   under the CI version or pin one.
6. **Local test failures, not caused by the branch**: `rdf_persistence/generation/__pycache__/`
   left from an old checkout (fails `test_packaging` and one `test_old_paths_gone`), and the
   `.worktrees/` copies scanned by `test_technical_split`. Removing the stale folder and the
   worktrees clears them.
