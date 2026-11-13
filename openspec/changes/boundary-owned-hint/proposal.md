<!-- Parents: GitHub issue #72; openspec/specs/rp-generation ("Generation fails on boundary
     violations"). -->

# EPIC: The boundary REFERENCE problem names its fixes

> Shaped and planned 2026-11-12 from issue #72. Independent of every other change; can run any
> time (a filler between stages).

**Golden-thread parent:** issue #72; capability `rp-generation`.

## Appetite

**TINY.** One message in `generation/checks/boundary.py`, its test, and one docs example.

## Why

The boundary check's REFERENCE problem says what is wrong ("slot `items` of `Terms` points to
`Term`, which is neither a root nor a reference class") but not how to fix it. In a technical
module the usual fix is to annotate the slot `owned: true`; a consumer's builder found that only by
reading the check's source.

## Solution outline

The problem text names both ways out, and the generation docs show a nested response class:

> slot `items` of `Terms` points to `Term`, which is neither a root nor a reference class: annotate
> the slot `owned: true` to hold `Term` inline, or make `Term` an aggregate root, or point the slot at a root, `Principal` or `Activity`

## Key decisions

- **DEC-1**: The hint is appended to the existing message of `BoundaryRule.REFERENCE`, so the rule
  id and every consumer's parsing stay the same. Rejected: a separate "fix" field on the problem
  (no other rule has one; `generation-fix-hint` already set the message as the place for fixes).

## Rabbit-holes

- None: the message is built in one place (`_reference_problems`).

## No-gos

- No change to what the check accepts or refuses.
- No new annotation.

---

## What Changes

- `rdf_persistence/generation/checks/boundary.py`: the REFERENCE message gains the fix.
- `docs/modules/ROOT/pages/architecture/generation.adoc`: a nested response class with
  `owned: true` in the modules paragraph.

## Capabilities

### Modified Capabilities

- `rp-generation`: the REFERENCE problem names the `owned` annotation as a fix.

## Impact

- Message text only; rule id unchanged.
