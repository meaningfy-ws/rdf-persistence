<!-- PLAN (design half), retrospective: it records what was built in PR #287. EPIC:
     abstract-collection-member-class (proposal.md, #274). -->

# Design: an abstract collection leaves its member class to its subclasses

## Context

`use_toolkit_slots` (`rdf_persistence_generation/uml/slots.py`) asks `_member_roles` for the
`dct:hasPart` usages that name a collection's member class. `_kept` skips the range line for
those usages, and `_fix_member_classes` writes one `equals_string` per holder. Nothing looked at
the class hierarchy, so a parent and its subclass both got one.

## Decisions

- **PD-1 (DEC-1, DEC-2):** `_member_roles` returns its usages through
  `_without_narrowed_parents`. For each holder, the nearest ancestor (domain `is_a`, `_lineage`)
  that also holds a member role is its parent. A parent that is abstract (`ClassDefinition.abstract`)
  is removed from the member roles. Its usage then reaches `_kept` as a plain toolkit slot, so
  the `toolkit-slot-kept … range … is not carried` line is written by the existing code, and
  `_fix_member_classes` never sees it.
- **PD-2 (DEC-3):** when the subclass's target is not in the `_lineage` of the parent's target,
  `ctx.findings.problem(UmlRule.TOOLKIT_SLOT, <subclass>, "dct:hasPart role to <X> does not narrow
  <parent>'s member class <Y>: …")`.
- **PD-3 (DEC-4):** a concrete parent is not removed. It is still checked by PD-2.
- **PD-4:** docs per P-0014: `reference/uml-conventions.adoc#member-class` and its troubleshooting
  table.

## Test specification

| Id | Tier | Test | Proves |
|---|---|---|---|
| TC-1 | unit | `ROWS_MEMBER_CLASS` "an abstract collection whose subclass draws its own member role fixes none; the subclass does" | PD-1, the kept line |
| TC-2 | unit | "an abstract collection whose subclasses draw no member role keeps its member class" | DEC-2 |
| TC-3 | unit | "failure: a subclass's member class that does not descend from the parent's names both" | PD-2 |
| IT-1 | integration | `test_uml_generate.py::test_an_abstract_collection_narrowed_by_its_subclass_type_checks` | the converted shape generates and type-checks; red on the parent commit |

## Risks

- **RISK-1:** a model where the descent goes through a mixin, not `is_a`, would fail PD-2. No
  known model does this. If one appears, it gets its own issue.
