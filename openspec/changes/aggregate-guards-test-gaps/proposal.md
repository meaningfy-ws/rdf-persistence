<!-- Parents: archive/2026-11-24-aggregate-guards (#305, #309), design.md D-11 and D-14: the review
     findings left under the floor. Opened 2026-11-24 at the developer's request ("fix the findings
     first"). -->

# EPIC: close the test gaps aggregate-guards left under the floor

## Appetite

**TINY.** Tests, one docs paragraph and no production change unless a test finds a defect. One
stage, one PR.

## Why

The two review passes of `aggregate-guards` left nine findings under the floor (design.md D-11,
D-14). The code paths exist but no test pins them, so a later change could break the reader's
cache, the remove-then-add path, tenant deletion or a real cascade without a test failing.

## Solution outline

One test per finding, red first where the code allows it (a test of existing behaviour is proven
by breaking the line it pins, then restoring it), and the missing sentence in `access.adoc`.

## Key decisions

- **DEC-1:** a test that pins existing behaviour is shown to fail by temporarily breaking the line
  it guards; the report names the line and the failure. No production change is kept unless a test
  finds a real defect, and then it stops and is reported (P-0019).
- **DEC-2 (R2-S2):** the stale-`If-Match` swap stays on any `Conflict` from a delete rule's run,
  not only `Refused`: with a stale version, the version conflict is the true answer whatever
  refused. A test pins it for a reader's plain `Conflict`.

## Rabbit-holes

- A cascade test through `delete_cascade` needs a collection in the toy; reuse what
  `reference_collections` tests already build.

## No-gos

- No new behaviour; no change to the public API.

---

## What Changes

Tests in `tests/unit/collaboration/test_aggregate_validators.py`, `test_write_guards.py`, the
collection and tenancy test modules; a paragraph in `user-manual/access.adoc`; scenario-map rows.

## Capabilities

None: the behaviour is specified in `rp-service-api` already. Archived with `--skip-specs`.
