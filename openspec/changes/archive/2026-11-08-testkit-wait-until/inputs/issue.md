<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

Copied verbatim from GitHub on 2026-11-08.

# Issue #24: testkit: wait_until is documented as public but not exported from rdf_persistence.testkit

https://github.com/meaningfy-ws/rdf-persistence/issues/24

## Summary
The testing checklist tells application tests to wait for eventual consistency with `testkit.wait_until`, but `rdf_persistence.testkit` does not export `wait_until`. It exists only in the internal module `rdf_persistence/testkit/bootstrap.py`, which consumers may not import (`rp-package-boundaries`: public API only).

## Context
- Consumer: MWB2 (mapping-workbench-v2), branch `docs/development-methodology`, while writing its testing checklist (the consumer's copy of `develop/testing.adoc`).
- The consumer's container and end-to-end tests need to wait on a condition with a deadline instead of sleeping; the toolkit's checklist says to use `testkit.wait_until`, and the consumer's boundary rule forbids importing `rdf_persistence.testkit.bootstrap`.
- rdf-persistence commit: `e5ca99d116338f0d06530fe127493f1c3c5d3a67` (develop).

## Current behaviour
```python
from rdf_persistence.testkit import wait_until
# AttributeError: module 'rdf_persistence.testkit' has no attribute 'wait_until'
```
`docs/modules/ROOT/pages/develop/testing.adoc`, rule 11: "wait for eventual consistency with `testkit.wait_until`". `rdf_persistence/testkit/__init__.py` `__all__` does not list it.

## Expected behaviour / proposed capability
Export the helper from the public test module, as the checklist promises:
```python
from rdf_persistence.testkit import wait_until

def test_the_uploaded_file_is_listed(client, tenant):
    upload(client, tenant, "a.csv")
    listing = wait_until(lambda: list_files(client, tenant) or None, "the file listing",
                         timeout=10, retry_on=())
    assert listing[0]["label"] == "a.csv", "the uploaded file is listed"
```
- Same signature as today (`probe`, `what`, `timeout`, `retry_on`, injected `sleep` and `monotonic`), raising `TimeoutError` naming `what`.
- Worth considering in the same change: an async twin (`await wait_until_async(probe, ...)`) for applications whose services and clients are async (FastAPI, `httpx.AsyncClient`); otherwise each application writes its own.
- Alternatively, if the helper is meant to stay internal, fix the checklist so it does not point applications at it.

## Why it belongs in rdf-persistence
Every application that runs the toolkit's container fixtures or its own end-to-end tests needs the same "poll a condition with a deadline, injected clock" helper; the toolkit already has a tested one. Copying it into each application duplicates toolkit code, and importing the internal module breaks the public-API rule.

## Acceptance
- **Given** an application test module, **when** it runs `from rdf_persistence.testkit import wait_until`, **then** the import succeeds and `assert_public_imports` accepts it.
- **Given** a probe that never succeeds, **when** `wait_until` times out, **then** it raises `TimeoutError` naming the thing waited for.
- **Given** the testing checklist, **when** a reader follows rule 11, **then** the name it cites is importable from the public test module.

## Impact on the consumer
Nothing is blocked yet (the consumer's project setup has not started); its testing checklist says "poll a condition with a deadline" without naming the helper until this is resolved.

