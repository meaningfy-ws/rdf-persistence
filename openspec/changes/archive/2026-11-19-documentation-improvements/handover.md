# Handover (2026-11-19)

Delivered in two PRs: #180 (structure, tutorial, manual split, checks; merged into develop after
thematic-structure stage 7) and the follow-up on `docs/documentation-finishing` (the polish of the
architecture explanations, the how-to guides and `questions.adoc`, the fixes below, and this
archive).

## Gates on the follow-up branch

| Gate | Result |
|---|---|
| `make check-quality` (with `check-docs`: links, anchors, fresh reference) | pass |
| `make test-generator` | pass |
| `make test-changed` | 8189 passed; 4 failed, local only (below) |
| `make check-diagrams` | pass |
| Docs and CI workflows on #180 | green |

## Fixed in the follow-up

1. `rp-generate --help` names the real `[tool.rp-generate]` key of each override flag
   (`tests/generator/unit/test_generate_cli_help.py`); the generated reference follows.
2. The example IRI policy is generic (`https://example.org/`, `library/` templates) in
   `user-manual/iri-policy.adoc` and in the tests (`EXAMPLE_POLICY`, formerly `CONSUMER_POLICY`).
3. "`kit.session` calls `open_session`" was verified: `ServiceKit.session` →
   `tenancy.tenant_session` → `_routed_session` → `Tenancy._session` → `open_session`.
4. The rp-generate usage is a table built from the parser, identical on Python 3.12 and 3.13; the
   docs workflow installs the project (it imports the package for the reference check).
5. A second cold review (four readers: app developer, architect, API client, contributor) found
   12 issues, all fixed: a new `reference/http-api.adoc` with the whole client contract and a
   generated table of problem types; complete routes and service kit tables; the one-process
   limit in the platform fit; a warning that the IRI policy is fixed at the first start; the
   settings behind each limit; one start-up order (`data-flows.adoc#migrations`); the generator's
   four check steps; `rp_writes: toolkit`; a generic, well-shaped event-stream example.

## Still open

- **Antora warning, older than this change**: `architecture/generation.adoc` reports "id assigned
  to anchor already in use: tool.rp-generate" twice; its cause is not found.
- **Toy tenant IRIs** under the example policy read `.../library/library/<id>` (the toy's base
  ends in `library/`); harmless, could read better.
- **`data-flows.adoc`'s "Rules and checks" table** overlaps `api.adoc#anatomy`; merging them is a
  structural choice left to the developer.
- **Local test failures, not caused by the branch**: stale `__pycache__` folders of removed
  packages (`test_packaging`, `test_theme_layout`, one `test_old_paths_gone`) and `.worktrees/`
  copies scanned by `test_technical_split`. A clean checkout passes.
