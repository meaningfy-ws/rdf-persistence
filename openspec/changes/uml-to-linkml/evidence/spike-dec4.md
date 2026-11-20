# SPIKE-1 evidence: may an application aggregate root be `is_a: Activity`? (DEC-4, task 1.7)

## Verdict

**Pass.** S-1..S-6 are green and no file under `rdf_persistence/` or `rdf_persistence_generation/`
changed (`git diff --stat -- rdf_persistence rdf_persistence_generation` is empty). Per PD-17 and
PD-18 the converter may allow `Activity` as `is_a` of a root, and never narrows a toolkit-filled
slot (PD-26). `Review` stays in the toy as the permanent guard (PD-34).

Base commit `8f64ccd9`.

## The probe

`Review` added to `tests/fixtures/library/books_activities.yaml`: `is_a: Activity`,
`mixins: [AggregateRoot, Described, Tracked]`, `rp_path: reviews`, with title and description.

## Results

| Id | Assertion | Test | Red before the toy change | Result |
|---|---|---|---|---|
| S-1 | `rp-generate` generates the toy with `Review` | `make generate` | n/a | exit 0: "generated 24 target(s), no problems" and "generated 1 target(s), no problems" |
| S-2 | a `slot_usage` on `started_at_time` of `Review` gets one `toolkit_filled` problem naming class and slot | `tests/generator/unit/test_hard_check.py::test_a_root_that_is_an_activity_may_not_narrow_started_at_time` | failed: `Review`'s anchor not in `books_activities.yaml` | green |
| S-3 | commit of a `Review`: one new `rp:Add`, `urn:uuid:` id different from the review's, one generation of the review as `lib:Review`, nothing about the review in the provenance graph | `tests/unit/provenance/test_activity_root.py::test_s3_committing_a_review_records_one_separate_add_generating_the_review` | `ImportError: Review` | green |
| S-4 | read back: equal model, `started_at_time` kept | `...::test_s4_a_review_reads_back_equal_with_its_start_time` | `ImportError` | green |
| S-5 | the event hub is offered exactly one activity, an `Add` | `...::test_s5_the_event_hub_is_offered_exactly_one_add_for_the_commit` | `ImportError` | green |
| S-6 | `POST /libraries/{t}/reviews` with `started_at_time` gives 201; `GET` returns it | `tests/unit/api/test_activity_root_routes.py::test_s6_a_review_is_posted_with_its_start_time_and_read_back` | `ImportError` | green |

Note on S-4: the comparison leaves out the `Tracked` stamps (`created`, `creator`, `modified`,
`contributor`), which the toolkit fills at commit; `creator` is asserted separately. A first
version compared the whole model and failed on those stamps: a test mistake, not a finding.

## Commands and counts

- Red run (before the toy change): `uv run pytest` of the two new library files: 2 collection
  errors (`ImportError: cannot import name 'Review'`); S-2: 1 failed.
- `make generate`: exit 0, 2 m 0 s.
- `make refresh-snapshot`: exit 0, 37 passed. `make refresh-served-golden`: ran, goldens
  `golden/openapi/openapi.json` (+1150 lines: the `/libraries/{t}/reviews` routes) and
  `golden/served_typescript/books_activities.ts` (+28) changed. `make refresh-map`: exit 1 by
  design (it lists the collected tests with no scenario row); 0 rows removed; the 7 new ids
  with no row are listed in the report (S-2..S-6, and the two tests of SPIKE-2).
- Diffs reviewed: every changed fixture file is a `Review` addition. `shapes.ttl` shows a large
  line diff (2229 lines) from reordering of the generated output; `schema.lock.json` gains 178
  lines (the new class); `model-shape.yaml` gains 50 lines (the `Review` shape).
- `tests/generator/unit/test_boundary_check.py`: the TC-102 `activity-root` row now keeps only
  its `book_slot_over` edit; `REVIEW_ROOT` removed.
- First `make test-fast check-quality`: 5 failed, 8311 passed, 2 xfailed. All five were tables
  that list the toy's roots and now need `Review` (RISK-7): `test_openapi.py` (route table),
  `test_documents.py` (two ids), `test_allowed_actions_adversarial.py`,
  `test_ext_jsonld_context.py` (frames). Each table got its `reviews`/`Review` row; no library
  code changed.
- Second `make test-fast check-quality`: exit 0; 8326 passed, 0 failed, 2 xfailed; quality
  checks all passed (17 contracts kept, 0 broken).
- Final run: `uv run pytest tests/unit/provenance/test_activity_root.py
  tests/unit/api/test_activity_root_routes.py tests/generator/unit/test_hard_check.py
  tests/generator/unit/test_boundary_check.py`: 265 passed, 0 failed, 0 xfailed, 12 s.
