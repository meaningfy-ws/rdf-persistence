# Acceptance: delete-refuses-referenced

**Verdict: accepted by the owner, 2026-11-21.**

**Shown:** the EPIC's use case over HTTP on the toy app at the stage-2 head (a63f4853), caller
`ada`, one tenant: eight steps, all as specified.

| Step | Expected | Actual |
|---|---|---|
| E3 an author nobody refers to | 204 | 204 |
| E1 a readable book `written_by` the author | 409 `in-use` naming (B1, Book, written_by); author stays | as expected; GET 200 |
| E2 the only referrer unreadable | 409, `referrers: []`, `hidden_count: 1`, no IRI of it | as expected |
| stale `If-Match`, referenced | 409 `conflict` | 409 `conflict` |
| E8 a shelf naming the author | 409 naming (shelf, Shelf, has_part) | as expected |
| E9 a comment on the author | 204, comment gone | as expected |
| E4 Book (not annotated) | 204 | 204 |
| retry after the referrer is gone | 204 | 204, then GET 404 |

Transcript and script were kept in the session scratchpad (`demo/transcript.txt`,
`demo/demo_refuse_referenced.py`); the same cases are the unit tests of
`tests/unit/api/test_delete_in_use.py` and the integration tests of
`tests/integration/store/test_referenced_removal.py`.

Open follow-ups at acceptance: #226 (a comment added in the commit that removes its target),
#227 (structural tidy-ups under the delivery floor).
