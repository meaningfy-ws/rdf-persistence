# Acceptance: reference-filters

**Status:** skipped by the developer, 2026-11-25 (MEDIUM: the demo may be skipped). The tests below
stand as the verification.

**Success measure (EPIC):** a consumer lists the aggregates whose referenced aggregate has a value,
paged and counted correctly, for example `GET /books?written_by.label=Frank Herbert`.

**What the delivery already shows (verification, not validation):**

- Through `GET` on Fuseki (`tests/integration/api/test_listing.py`,
  `test_a_filter_through_references_lists_and_counts_against_fuseki`): one and two references
  (S1, S3b), with `total`; `make test-containers` 362 passed, 2026-11-25.
- Through `GET` on the in-memory store (`tests/unit/api/test_listing_routes.py`): S1, and S4 (an
  author the caller is prohibited from reading hides the book from the page and the total).

**Demo, if taken:** run the toy service, POST an author and a book written by it, then
`GET /books?written_by.label=<label>` and `GET /books?written_by.label~=<part>`, and the same with a
read Prohibition on the author's graph.

**Verdict:** skipped, by the developer, 2026-11-25.
