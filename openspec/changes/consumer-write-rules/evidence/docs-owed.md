# Docs owed: consumer-write-rules

No docs owed (the lead, 2026-11-28). The EPIC changes user-facing behaviour, and every page it
touches was updated inside the build stages, each checked by `make check-docs` and by the stage's
checker as cold reader:

- `architecture/generation.adoc` (technical imports, `Problem` as the extension point), `architecture/index.adoc` (the import map), `architecture/api.adoc` (the refusal and `find` rows): tasks 1.5, 2.5, R-W1, F-4 pass.
- `user-manual/access.adoc` (refusing with your own problem, `find`, typed rules, `state_name`, testing a rule): tasks 1.5, 2.5, C-2, the fix pass.
- `user-manual/test.adoc` (the fake reader and the reader conformance kit): task 2.5, F-4.
- `CHANGELOG.md` (Added, and the BREAKING line for `AggregateReader.find`): tasks 1.5, 2.5.

Owed elsewhere, not here: the OpenAPI document's listing of registered problem classes goes back to
shaping with task 1.4 (D-5), and its docs with it.
