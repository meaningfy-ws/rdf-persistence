<!-- Parents: GitHub issue #24; openspec/specs/rp-testkit/spec.md;
     docs/modules/ROOT/pages/develop/testing.adoc rule 11. Seeds: inputs/issue.md, inputs/seed.md. -->

# EPIC: Export `wait_until` (and an async twin) from the testkit

**Golden-thread parent:** GitHub issue #24 and the `rp-testkit` capability; the testing checklist
(`develop/testing.adoc`, rule 11) promises a name the public test module does not export.

## Appetite

**TINY.** One concern in one place: make the promised helper public, add its async twin, and keep
the checklist true.

## Why

The testing checklist tells applications to wait for eventual consistency with
`testkit.wait_until`, but `from rdf_persistence.testkit import wait_until` fails: the helper lives
only in the internal `rdf_persistence.testkit.bootstrap`, which consumers may not import
(`rp-package-boundaries`). Each application would otherwise copy the helper, and the async ones
(FastAPI, `httpx.AsyncClient`) would write their own async version too.

## Solution outline

`rdf_persistence.testkit` exports `wait_until` with its current signature and behaviour, and a new
`wait_until_async` that does the same for an async probe. The checklist and the public API table
name both. The container fixtures keep using the same function.

## Key decisions

- **DEC-1**: Export `wait_until` from `rdf_persistence.testkit` unchanged (signature, `TimeoutError`
  naming `what`, default timeout and poll interval). Source: issue #24. Rejected: rewording the
  checklist to keep the helper internal.
- **DEC-2**: Add `wait_until_async` to the same public module, mirroring `wait_until` with an
  awaited probe and an injected async sleep. Source: developer, 2026-11-08 (`inputs/seed.md` Q1).
  Rejected: export only.
- **DEC-3**: The testkit root stays light: exporting either name imports no heavy library (the
  existing lazy-import tests stay green). Source: `rdf_persistence/testkit/__init__.py` docstring.

## Rabbit-holes

- Generalising into a retry library (back-off, jitter, attempt counts). The helpers poll at a fixed
  interval until a deadline; nothing more.
- Moving `bootstrap.py`. The module may stay where it is; only the public names matter.

## No-gos

- No change to `wait_until`'s signature or defaults.
- No new runtime dependency (`asyncio` only).
- No async versions of the other testkit helpers.

---

## What Changes

- `rdf_persistence/testkit/__init__.py`: export `wait_until` and `wait_until_async`.
- `rdf_persistence/testkit/bootstrap.py`: add `wait_until_async`.
- `docs/modules/ROOT/pages/develop/testing.adoc` rule 11 and the public API table in
  `docs/modules/ROOT/pages/architecture/index.adoc` name both helpers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-testkit`: adds the requirement that the waiting helpers are public.

## Impact

- Public API of `rdf_persistence.testkit` grows by two names; nothing removed.
- No change to the package's runtime dependencies or to the service.
