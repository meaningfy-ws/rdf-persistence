# Q&A record: aggregate-composition (secondary; never groomed)

Shaped with the developer, 2026-11-28, from #437 (`seed.md`), #435 (`seed-435.md`), the consumer's
decisions S8-14..S8-17 (`consumer-decisions.md`), its rules (`consumer-rules.md`), its model rules
and conventions README (`consumer-model-rules.md`) and its check script (`qea_conventions.py.txt`).

## Facts read before asking

- The converter already reads composition as a composite **association** end: `links.py`
  `_is_owned` / `_ends` (`source_aggregate == COMPOSITE`). It refuses EA's separate **Aggregation**
  connector type (`qea.py` `LINK_KINDS`, a `no_rule` problem).
- Owned slots also come from boundary geometry: `links.py` `owned_pairs` / `_boundary_pairs`
  (a boundary with exactly one «root» or «tenant root» makes every member-to-non-root pair owned).
- Loaded graphs already exist at runtime: `Session.load_graph` registers a raw-RDF graph to an
  aggregate; `Session.delete` removes the aggregate's graph, loaded graphs and registry entries
  (`session.py` l.1135, l.1232). A part of a `--not-generated` stereotype under «own graph» maps
  onto this.
- A generated class as an «own graph» part (own graph and version token, written separately,
  deleted with its whole) has no runtime support: it is a new library capability.
- The consumer's check script hard-codes its package list, banned attributes and toolkit tags; it
  must be rewritten generically, not copied.
- rdf-persistence's rule ids P-0001..P-0024 collide with the consumer's P-0007..P-0027; adopted
  rules get new ids here.

## Round 1 (2026-11-28, answered)

| Id | Question | Answer |
|---|---|---|
| Q1 | How is #437 cut into changes? | Two changes: `aggregate-composition` (converter, conventions, check; #435 folded in; «own graph» to loaded-graph parts) and `dependent-aggregates` (the generated «own graph» part at runtime), planned after it. |
| Q2 | What is a generated «own graph» part at runtime? | A dependent aggregate: own graph, version token, API resource and `rp_path`, a required pointer to its whole, deleted with the whole in the same transaction. (Shaped in `dependent-aggregates`.) |
| Q3 | The existing composite-association form? | **Refuse it.** Only the two-connector form (a composition beside its association) is accepted. Breaking. |
| Q4 | Where does the conventions check live? | Inside the converter: each convention is a problem or report line; `rp-uml2linkml --check` reads and reports without writing; consumer-specific checks stay in the consumer and reuse the public qea reader. |

## Round 2 (2026-11-28, answered)

| Id | Question | Answer |
|---|---|---|
| Q5 | «root» and boundaries during the transition? | Accept and check agreement: a «root» that disagrees with the derived roots is a problem, an agreeing one a `deprecated-root` report line; boundary geometry is never read, a boundary disagreeing with the compositions is a report line. |
| Q6 | A generated «own graph» part before `dependent-aggregates` ships? | A problem naming the follow-up change; only a `--not-generated` part is accepted under «own graph». |
| Q7 | Where do the adopted rules and conventions live? | Rulebook + guide: P- notes in `docs/rules/` (new ids, `activity:modelling`, generic wording, the source quoted); the guide holds the conventions, terms and deletion test with UML snippets and links the rules without restating them. |
| Q8 | Risks to plan for? | All four: EA connector direction (read the diamond end, not the drawing direction); a consumer redrawing before the release (transition keeps «root» models converting byte-identical, release notes give the migration); rule drift between the copies (accepted, the consumer retires its copies in its next model round); output changing when a model is redrawn (golden test: one model drawn both ways, identical output). |

## Round 3 (2026-11-28, answered)

| Id | Question | Answer |
|---|---|---|
| Q9 | What must the change prove? | All four groups: composition core (owned/inlined slot, depth-3 nesting, missing association, cycle, two wholes, unreachable part); derived roots (exclusions, report, disagreeing «root», layout-only boundary move byte-identical); «own graph» and pointers (loaded-graph part accepted on the validation example, generated part refused, pointer into another aggregate's part refused, composite association refused); `--check` and #435 (writes nothing, C-1..C-12 each fail on a seeded model, aggregates diagram holding an association reported, Realisation accepted, disagreeing Realisation a problem). |
| Q10 | Severity of a presentation convention? | A report line in a normal conversion (it still writes); `--check` exits 1 on any convention line; meaning conventions (tree, pointers, roots) are problems in both modes. |
| Q11 | Shape `dependent-aggregates` here too? | Yes, both shaped and planned in this session. |

## Lead's decisions, not asked (2026-11-28; the developer reviews them with the PLAN)

- DEC-6 sharpened: when a model draws «root» at all, the drawn set must equal the derived set.
- DEC-10: the consumer's C-7 (boundaries) is replaced by DEC-6, and the acyclic-imports half of
  its C-6 is not ported, because `rp-uml-import` supports packages that import each other.

## Re-shape of DEC-4 (2026-11-28, lead, during delivery under the developer's grant; to validate)

The PLAN attack (`evidence/attack.md`, A-1 critical, A-2 critical) showed that a class-level tree
("a part with two wholes is a problem", "a cycle is a problem") refuses recursive parts
(`Section ◆ Section`, today owned through a boundary) and one part type under two wholes (the
consumer's RML `GraphMap` under `SubjectMap` and `PredicateObjectMap`, both inside one
`TriplesMap`). The issue's "a part has exactly one whole" holds for instances, which is what
storage needs: an instance is inlined in exactly one whole's graph. DEC-4 now states the
instance-level tree. A part class unreachable from any root, a part drawn «root», and a cycle no
root enters stay problems. This is an EPIC-level change, logged here and in DEC-4; the developer
was away and had granted delivery to the end.

## Amendment of DEC-2 (2026-11-28, lead, after the clarity gate's G-5; to validate)

DEC-2 said "a composition with two candidate associations is a problem". The attack's A-3 showed
legitimate models with two owned roles to one part class, and one owned role plus an internal
reference. A role written on the composition now names the association it marks owned. No
candidate, or several and no role, stays a problem (design.md D-6).

## Readiness check (lightweight, 2026-11-28): pass

Appetite, why, outline, DEC-1..DEC-12, rabbit-holes and no-gos present; no undecided bet-level item.
