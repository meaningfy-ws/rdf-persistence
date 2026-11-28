# Q&A record: workflow-assignees (#426)

Secondary input, kept as asked and answered on 2026-11-27, one round. The EPIC (`proposal.md`)
is the shaped truth. Seed: `seeds/issue-426.md`.

Read before asking: `rp-workflow`, `rp-access`, `rp-service-api` specs; `model/rp_workflow.yaml`,
`rp_access.yaml`, `rp_annotations.yaml`; `collaboration/services/transitions.py`,
`workflows.py`; `tenancy/services/tenancy.py` (`set_grants`); `access/services/access.py`
(`load_caller_access`); the in-flight `fine-grained-access` EPIC (no overlap).

## Q1: Slot name and IRI
- Asked because: `assignee` is already `odrl:assignee` in `rp_access`.
- Answer: recommendation accepted: `assigned_to`, `rp:assignedTo`, range `Principal`,
  multivalued, on the `UnderWorkflow` mixin.
- → DEC-1

## Q2: Who owns the slot
- Asked because: an ordinary slot would let any `modify` write it with no record.
- Answer: recommendation accepted: the toolkit owns it like the state; a plain write may not
  change it; only the assign call (and a clearing transition) does.
- → DEC-2

## Q3: Who may assign
- Asked because: the issue says "the workflow decides who may assign".
- Recommended: `assign_roles` in the workflow file.
- Answer (developer's exception): like Jira. Whoever may edit the entity (`modify`) may change
  its assignees; a caller who may only read, comment or move it (a reviewer) may not.
- Carried from the recommendation, not contradicted: the workflow file still says whether
  assignment applies at all (`assignable`), as the issue asks.
- → DEC-3, DEC-4

## Q4: Self-assignment
- Asked because: a reviewer without `modify` would otherwise never pick up work.
- Recommended: no.
- Answer (developer's exception): yes. A principal who may move the aggregate out of its current
  state (holds a role on such an edge) may add or remove themselves.
- → DEC-4

## Q5: Transitions and assignment
- Answer: recommendation accepted: an edge may only clear (`clears_assignees: true`); setting
  assignees in a transition is out.
- → DEC-5

## Q6: Who may be an assignee
- Answer: recommendation accepted: a principal who may `read` the aggregate when assigned.
- → DEC-6 (the planner adds: decided from the stored grants and prohibitions; token global roles
  are not visible for another principal, see the PLAN)

## Q7: Access removed later
- Answer: recommendation accepted: (a) the grant change releases the principal's assignments,
  recorded. The planner found the grants live in the system database and the aggregates in the
  tenant database, so the release follows the grant change and is not atomic with it (RISK-1).
- → DEC-7

## Q8: The record
- Answer: recommendation accepted: an `Assignment` activity beside `Transition`;
  `assignments(iri)` oldest first.
- → DEC-8

## Q9: HTTP
- Answer: recommendation accepted: a service call only, as transitions; the listing filter comes
  from the generic listing.
- → DEC-9

## Q10: Version and frozen aggregates
- Answer: recommendation accepted: `if_version` required, the version changes, a Prohibition of
  `modify` blocks it.
- → DEC-10

## Q11: What the EPIC must prove
- Answer: recommendation accepted: assign two; refused without the right; refused for an assignee
  without access; a plain write cannot change them; a clearing transition; grants removed then
  released with a record; `?assigned_to=` gives one person's queue; a stale version conflicts;
  the history in order. No `@manual` check named.
- Added by Q3/Q4: a reviewer without `modify` takes and drops the work themselves, and cannot
  assign anyone else.

## Q12 to Q14: Risks (general questions)
- Answer: "accept, go ahead". The planner's risks (RISK-1 to RISK-4 in `design.md`) are recorded
  as accepted, with the cheap mitigations named.
