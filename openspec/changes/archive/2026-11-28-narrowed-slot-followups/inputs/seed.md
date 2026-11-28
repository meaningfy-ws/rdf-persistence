# Seed: GitHub issue #428 (secondary input)

Copied from meaningfy-ws/rdf-persistence#428 on 2026-11-28; the issue is the primary record.

> **narrowed-slot-override follow-up: rule-5 and mypy test gaps, dict-rendered keyed slot**
>
> Follow-up of `narrowed-slot-override` (PR #427, #417): the review pass (L2+L3) found no Critical
> defect; these four findings fell under the floor (design.md D-8) and are collected here.
>
> - **W1, tests for PD-2 rule 5.** The marked side of rule 5 has no case for classes or types:
>   "both single, class range not under the ancestor's", "`uri` against `string`", "class against
>   type or enum" (design.md error matrix). A broken class or type branch in `_is_under`
>   (`rdf_persistence_generation/extensions/pydantic_split.py`) passes the suite. Add those cases
>   to `test_a_field_overriding_a_slot_incompatibly_carries_a_type_ignore_and_only_then`.
> - **W2, mypy proof of scenarios 1 and 2.** TC-1 narrows multiplicity and requiredness but keeps
>   the range, and no test runs mypy over a compatible covariant single-slot override (scenario 2
>   is proved by "no mark" only). Have TC-1's subclass narrow to a subclass of `Part`, and add a
>   covariant single-slot child to the same project.
> - **S1, a keyed slot rendered as a dict.** `keyed_slots` admits a multivalued slot with
>   `inlined: true`, no `inlined_as_list`, over a class with an identifier, which LinkML renders as
>   a `dict`. The PD-5 loop wraps an explicitly empty `{}` as `[{}]` and raises `AttributeError`;
>   the old `or []` passed it (a non-empty dict failed before as well). Decide: iterate `.values()`
>   for a dict, or refuse such a keyed slot in `keyed_slots`.
> - **S2, two error-matrix rows untested.** "Identifier or key slot: never marked" and "narrowed
>   keyed slot left absent iterates `[]`". Add one unit case and one optional `OneKeyedHolder`
>   built without `parts`.
