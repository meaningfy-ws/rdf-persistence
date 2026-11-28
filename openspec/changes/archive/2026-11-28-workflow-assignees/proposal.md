<!-- Parents: capability rp-workflow (and rp-access for who may act); issue #426.
     Seeds: inputs/seeds/issue-426.md; Q&A: inputs/qa.md. Serves the consumer need named in #426
     (an "assigned to" column and filter on a listing of workflowed entities); the consumer's own
     change names this change id (D-12). -->

# EPIC: Assignees on aggregates under a workflow

## Appetite

**MEDIUM**: one new capability on the existing workflow (a toolkit-owned slot, one call, one
record, one release rule), with the write guard, the transition and the grants route touched
lightly. Two stages.

## Why

An aggregate under a workflow cannot say who is to work on it next: the workflow gives states,
the roles allowed to move it and the history; the annotations give creator and contributor;
nothing names the person or people the work is assigned to. A consumer adding its own slot per
class would repeat it in every model and could not tie it to the workflow's rights or history.

## Solution outline

A workflow file may declare itself `assignable`. An aggregate under such a workflow then holds
zero, one or more assignees: principals who may read it. Whoever may modify the aggregate changes
its assignees with one call; whoever may move it out of its current state may take it or drop it
for themselves. Each change is recorded in the provenance graph, like a transition. An edge may
clear the assignees as it moves the aggregate. When a grant change takes away a principal's read
access, the toolkit releases the principal from what it can no longer read, and records that too.
A person's own queue is one listing: `?assigned_to=<principal IRI>`.

## Key decisions

- **DEC-1**: The slot is `assigned_to` (`rp:assignedTo`), range `Principal`, multivalued,
  optional, on the `UnderWorkflow` mixin. Reason: `assignee` is `odrl:assignee` in `rp_access`; no
  standard term fits cleanly. Rejected: a consumer slot per class (#426).
- **DEC-2**: The toolkit owns the assignees, as it owns the state: a plain write that changes
  them is refused; a replace that omits them keeps the stored ones; a new aggregate holds none.
  Only the assign call and a clearing transition change them. Rejected: an ordinary slot any
  `modify` may write, which leaves no record and checks no assignee.
- **DEC-3**: Assignment is opt-in per workflow: `assignable: true` in the workflow file (absent:
  false). An aggregate under a workflow that is not assignable refuses every assignment except
  one to nobody, which clears what was stored while it was. Reason: #426 asks that the workflow say whether it applies; old workflow files
  keep their meaning.
- **DEC-4**: Who may assign, like Jira (developer, Q3/Q4): a caller who may `modify` the aggregate
  may set any assignees; a caller who may not, but holds a role on an edge leaving the current
  state, may add itself; any assignee may remove itself (planner's addition: otherwise a reviewer
  left on work in a final state could never drop it). A Prohibition of `modify` on the aggregate or the tenant
  blocks every assignment, self-assignment included. Rejected: `assign_roles` in the workflow
  file.
- **DEC-5**: A transition may only clear: an edge with `clears_assignees: true` removes every
  assignee as it moves the aggregate. Setting assignees during a transition is out.
- **DEC-6**: An assignee is a principal who may `read` the aggregate when assigned, as the stored
  grants and prohibitions of the tenant decide. Others are refused, naming the principal. Removing
  an assignee needs no check.
- **DEC-7**: When the grants of a tenant are replaced through the toolkit's grants route, the
  toolkit then releases every assignee who may no longer read its aggregate, and records each
  release. It follows the grant change and is not atomic with it (the grants and the aggregates
  live in different databases); the release is idempotent, so the next grant change repairs a
  release that was interrupted.
- **DEC-8**: Each assignment change is an `Assignment` activity (`prov:Activity`, a sibling of
  `Transition`) in the tenant's provenance graph, written in the same update as the change, naming
  the aggregate, the principals added and removed, the agent and the time. `assignments(iri)`
  lists them oldest first and they outlive the aggregate, as transitions do. A clearing
  transition records the released principals on its `Transition`.
- **DEC-9**: A service call only, `Collaboration.assign(iri, principals, if_version)`, as for
  transitions; no toolkit HTTP route. The person's queue is the generic listing filter on the
  slot.
- **DEC-10**: The assign call needs the version the caller read and changes it; a stale version
  is a conflict, checked first, as for a transition.

## Rabbit-holes

- **Two databases.** The grants are in the system database, the aggregates in the tenant's; the
  release cannot share the grant change's update (DEC-7). Do not build a cross-database
  transaction.
- **Global roles.** A principal's token roles are not visible when another caller assigns it;
  only stored grants count (DEC-6). A principal who reads only through a global role cannot be
  assigned. Do not try to resolve tokens.
- **A listing filter on a multivalued IRI slot.** Whether equality matches "any value" must be
  proved, not assumed.
- **Grant changes made elsewhere.** A migration's `grant_roles` or a direct `Tenancy.set_grants`
  call does not run the release (RISK-2).

## No-gos

- A toolkit HTTP route for assigning; notifications or e-mails to assignees.
- A listing of candidate assignees (who may be picked); the consumer reads the grants it may read.
- Assignment rules per state, workload limits, due dates or ordering of assignees.
- Assignees on aggregates under no workflow, or set at creation, or set by a transition.
- Any consumer term, model or code.

---

## What Changes

As delivered (PR #443, stage 1; PR #458, stage 2):

- `rdf_persistence/model/rp_workflow.yaml`: `assigned_to` on `UnderWorkflow`; `assignable` on
  `Workflow`; `clears_assignees` on `WorkflowTransition`; the `Assignment` activity (payload
  `assigned_to`, `expected_version`; toolkit-filled `assigned_principals`, `released_principals`);
  `released_principals` on `Transition`. Then `make generate`. `Assignment` is public (164 names).
- `rdf_persistence/collaboration/services/`: a new `assignments.py` (`assign`, `assignments`,
  `release_unreadable`); a new `aggregate_activities.py` (one reader of an aggregate's activities,
  shared with the transitions, its own import-linter layer, D-13); `workflows.keep_state` keeps the
  assignees through an exact allowed set (`Transaction._allow_assignees`, the `WriteGuard.prepare`
  keyword `allowed_assignees`, an internal port); the transition clears them;
  `Collaboration.assign`, `assignments` and `release_unreadable`.
- `rdf_persistence/core/domain/sparql.py`: `is_absolute_iri`, the check an added principal passes
  (D-18).
- `rdf_persistence/api/`: `ServiceKit.release_assignees`, run by `PUT …/grants` after its commit;
  `access_of` wired into `collaboration()`.
- Docs: `howto/workflow.adoc` (assign the work), `user-manual/access.adoc` (who may assign, the
  release, RISK-2, RISK-3), `architecture/data-flows.adoc` (the guard keeps the assignees),
  `CHANGELOG.md`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-workflow`: ADDED requirements for assignees, who may assign, the record, the clearing
  edge, the release on lost access and the queue listing.
- `rp-messages`: MODIFIED, the toolkit-filled slots gain `assigned_principals` and
  `released_principals` (found by the stage-1 review, D-19).

## Impact

- Generated classes, shapes, the JSON-LD context and the TypeScript types gain the new slots; an
  existing aggregate holds no assignees and is unchanged (no data migration).
- A grant change costs more than shaped: the release loads the graph of every aggregate that
  holds assignees, then reads again and commits each one it releases. A
  narrower scan (only the roots of principals whose access changed) is a follow-up (L5 #3, under
  the floor).

## Reconciliation (as delivered)

| Shaped | Delivered | State |
|---|---|---|
| DEC-1 `assigned_to` on `UnderWorkflow` | `rp_workflow.yaml`, generated classes, shapes, context, TypeScript | delivered, PR #443 |
| DEC-2 the toolkit owns the assignees | `workflows.keep_state` with an exact allowed set, checked before the stored one (RDF cannot tell omitted from empty) | delivered, PR #443 |
| DEC-3 opt-in `assignable` | `Assignments.assign` refuses a non-empty set under a workflow not assignable; an empty set clears | delivered, PR #443; the release ignores `assignable` by design, untested (L2 #3 under the floor) |
| DEC-4 who may assign, like Jira | `Assignments._require_authority`: modify sets anyone; a role on a leaving edge adds itself; any assignee drops itself; a Prohibition of modify blocks all | delivered, PR #443 |
| DEC-5 an edge may only clear | `clears_assignees`, `Transitions._moved(clear=True)`, the released principals on the `Transition` | delivered, PR #443 |
| DEC-6 an assignee may read | `_require_readers` by the stored grants, through `access_of`; principals checked as absolute IRIs (D-18) | delivered, PR #443; checked before the commit, not inside it (L1 #2 under the floor) |
| DEC-7 release after the grants route | `ServiceKit.release_assignees` after `PUT …/grants`; failure logged, 200 kept; idempotent | delivered, PR #458; only that route (RISK-2, L3 #1 under the floor) |
| DEC-8 the `Assignment` record | `Assignment` (`prov:Activity`) in the commit's update; `assignments(iri)` oldest first, kept after delete | delivered, PR #443 |
| DEC-9 a service call; the queue as a filter | `Collaboration.assign`; `?assigned_to=` on the generic listing, no code change (D-7, T15) | delivered, PR #443 and PR #458 |
| DEC-10 the version first | `if_version` checked after read and the Prohibition, before anything about the assignees; `Conflict` | delivered, PR #443 |
| Tests T1 to T16 | unit, adversarial and feature tests, scenario-map rows | delivered; T16 never red, since the release was built first (D-22) |
| Docs | howto, user manual, data flows, `rp-messages` delta, CHANGELOG | delivered, PR #458 |

Not shaped but built: `aggregate_activities.py` (D-13), `core/domain/sparql.is_absolute_iri`
(D-18), the `rp-messages` delta (D-19). Shaped but not built: nothing.
