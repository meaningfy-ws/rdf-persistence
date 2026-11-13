> Derives from: EPIC `boundary-owned-hint` (proposal.md, issue #72). Implements DEC-1.
> Type: Implementation.

## Context

`_reference_problems` (`rdf_persistence/generation/checks/boundary.py`) yields
`rule_problem(BoundaryRule.REFERENCE, name, f"of {cls.name} points to {slot.range}, which is neither a root nor a reference class")`.
`is_owned(slot)` reads the `owned` annotation. Tests: `tests/unit/generation/test_boundary_check.py`
(the REFERENCE cases near lines 56 and 72).

## Goals / Non-Goals

**Goals:** "The REFERENCE problem names its fixes" (`specs/rp-generation/spec.md`).
**Non-goals:** what the check accepts; other rules' messages.

## Decisions

- **PD-1** (DEC-1): the message becomes
  `f"of {cls.name} points to {slot.range}, which is neither a root nor a reference class: annotate the slot owned: true to hold {slot.range} inline, or make {slot.range} an aggregate root, or point the slot at a root, Principal or Activity"`.
  "Reference class" is a closed list (`REFERENCE_CLASSES = ("Principal", "Activity")`), so the
  message never tells a consumer to make its own class one (gate, 2026-11-12: 9/10, two minor
  findings, both folded in here).
- **PD-2**: the docs example goes in the *Modules* paragraph of `architecture/generation.adoc`
  (around "technical modules for concerns such as paging or API envelopes"), a YAML block with
  `Terms.items` ranged on `Term`, `inlined_as_list: true` and `annotations: {owned: true}`.

- **PD-3** (review, 2026-11-13): TC-01 also asserts `make Term an aggregate root`, and the test
  helper asserts the import line it rewrites exists. Rejected: building the message from
  `REFERENCE_CLASSES` and `RpAnnotation.OWNED` (PD-1 fixes the wording; a change to either list is
  rare and caught by TC-01).

## Algorithm / approach

One f-string. Worked example: issue #72's `Terms`/`Term` module gives
`slot items of Terms points to Term, which is neither a root nor a reference class: annotate the slot owned: true to hold Term inline, or make Term an aggregate root, or point the slot at a root, Principal or Activity`.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Add a new rule id for the hint | Extend the message (DEC-1) | Consumers match on rule ids |
| Recommend only `owned` | Name both fixes | In a domain module the range may need to be a root |

## Error matrix

| Input | Result |
|---|---|
| Not-owned slot to a non-root, non-reference class (any module kind) | REFERENCE problem with both fixes |
| Same slot with `owned: true` | no REFERENCE problem (unchanged) |
| Slot to a root or `Principal`/`Activity` | no problem (unchanged) |

## Risks / Trade-offs

- **RISK-1** — a test or consumer asserts the full old message (low; low). Mitigation: grep the
  tests for "neither a root"; the old text stays a prefix.

## Open Questions

None.
