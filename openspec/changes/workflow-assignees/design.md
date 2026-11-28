# Design: workflow-assignees

> Derives from: EPIC `workflow-assignees` (`proposal.md`, #426). Its DEC-1 to DEC-10 are cited
> here, not restated. The delivery decisions below are D-n, each a heading (`design.md#d-1`, …).

## Context

Code facts, read on `develop` at `801613ba`:

- **Workflow model.** `model/rp_workflow.yaml`: `Workflow` (l.24), `WorkflowTransition` (l.47,
  `transition_roles`, `comment_required`), the `UnderWorkflow` mixin with `workflow_status`
  (`adms:status`, l.65), and `Transition` (`is_a: Activity`, l.74) whose `to_state`,
  `expected_version` and `body_value` are command payload (`payload: true`).
- **The state guard.** `Workflows.keep_state` (`collaboration/services/workflows.py` l.133) keeps a
  plain write from changing `adms:status`: on add, a written state must be the initial one; on
  replace, one query (`session.root_values(iri, [RDF.type, WORKFLOW_STATUS])`) reads the stored
  state, an omitted state is put back, and a different one is refused unless the transaction
  allowed it with `Transaction._allow_state` (`persistence/services/session.py` l.1566).
- **The transition.** `Transitions.transition` (`collaboration/services/transitions.py` l.71)
  checks, in order: the module, `read`, a Prohibition of `modify`, the version (a `Conflict` that
  hides every refusal below it), the workflow, the edge and its roles (`AccessRules.roles`,
  l.180), the comment; then `_store` writes the graph and the comment in one transaction whose
  activity is the `Transition` record (l.224). `Collaboration.transition` delegates (l.197).
- **Access.** `AccessRules.may(caller, access, iri, action)` (`access/services/access.py` l.289)
  decides from a `VerifiedCaller` (principal, global roles) and a `CallerAccess` (tenant, state,
  grants, prohibitions). `load_caller_access(store, system_database, tenant, principal)` (l.129)
  reads the grants and prohibitions that name one principal, in one query.
- **Grants live in the system database**, in the tenant's access record.
  `Tenancy.set_grants` (`tenancy/services/tenancy.py` l.813) replaces them in one update there;
  the aggregates live in the tenant database. The grants route is
  `TenantApi.set_grants` (`api/entrypoints/router.py` l.320), wired at l.382.
- **Layers.** `.importlinter` orders the themes `api > messaging > collaboration | events >
  tenancy > access …` and, inside collaboration, `collaboration > transitions | write_guards |
  referenced_removals > discussion | … | workflows > access > session` (l.165-173).
- **Listings** filter by equality on any slot of the type (`rp-service-api`, "Listings are filtered
  and paged").
- **Test fixture.** `tests/fixtures/library/review.workflow.yaml`: states `draft`, `in_review`,
  `accepted`; every edge for `librarian`.

## Goals / Non-Goals

**Goals:** the seven ADDED requirements of `specs/rp-workflow/spec.md`, in two stages.

**Non-Goals:** the EPIC's no-gos; a cross-database transaction (Rabbit-holes); a change to how
`read` is decided.

## Decisions

### D-1

**Model.** In `rp_workflow.yaml`, then `make generate` (lead):

- `assigned_to`: `slot_uri: rp:assignedTo`, `range: Principal`, `multivalued: true`, on
  `UnderWorkflow` (DEC-1).
- `assignable`: `rp:assignable`, boolean, `ifabsent: "false"`, on `Workflow` (DEC-3).
- `clears_assignees`: `rp:clearsAssignees`, boolean, `ifabsent: "false"`, on `WorkflowTransition`
  (DEC-5).
- `Assignment`: `class_uri: rp:Assignment`, `is_a: Activity`, slots `used_resource` (required),
  `assigned_principals` (`rp:assignedPrincipal`, `Principal`, multivalued),
  `released_principals` (`rp:releasedPrincipal`, `Principal`, multivalued); command payload
  `assigned_to` and `expected_version` (`payload: true`), as `Transition` carries its own (DEC-8).
- `released_principals` also on `Transition` (DEC-8, the clearing edge).
- `WORKFLOW_ASSIGNEES`, `ASSIGNMENT` in `schema/services/vocabulary.py`, beside `WORKFLOW_STATUS`.

No data migration: the slots are optional and no stored aggregate holds them.

### D-2

**The guard.** `Workflows.keep_state` grows to keep the assignees with the state, in the same one
query (`root_values` reads `WORKFLOW_ASSIGNEES` too; no query is added). The rules, for the root
only (DEC-2):

RDF cannot tell "omitted" from "empty", so an allowed set is checked first and is exact:

| Write | Assignees written | Result |
|---|---|---|
| replace, the transaction allowed a set for this root | exactly that set (empty included) | written as is, nothing put back |
| replace, the transaction allowed a set for this root | any other set | `Forbidden` |
| replace, nothing allowed | none | the stored ones are put back |
| replace, nothing allowed | the stored set | written as is |
| replace, nothing allowed | any other set | `Forbidden` |
| add, any workflow | none | written as is |
| add, any workflow | some | `Forbidden` |
| replace that gives a workflow class to a root of none | held or written assignees | `Forbidden` (as `TAKES_A_CLASS`, `_taking_a_class` l.201) |

`Transaction._allow_assignees(iri, principals)` mirrors `_allow_state`: private, used by
`Assignments` and `Transitions` only, collects no change. It reaches `keep_state` through the
`WriteGuard.prepare` port (`session.py` l.557-566, called at l.1336, l.1442, l.1484) as a new
keyword-only `allowed_assignees: frozenset[str] | None = None`, beside the positional
`allowed_state`. The test double at `tests/unit/persistence/test_session_transaction.py` l.656
gains the keyword (a signature update, its assertions unchanged). A root of no workflow class is
not guarded (its `rp:assignedTo` is the application's, as `adms:status` is).

### D-3

**`Assignments`**, a new module `collaboration/services/assignments.py`, in the import-linter
layer of `transitions` (l.172; it imports `workflows`, `access`, `session`, never `transitions`).
`Collaboration.assign` and `Collaboration.assignments` delegate to it, as `transition` does.
`assign(iri, principals, *, if_version, command=None) -> str`, where `command` is the
`Assignment` to store (a consumer's subclass, say), exactly as the `command` parameter of
`Transitions.transition` (`transitions.py` l.78): the computed slots overwrite its own. It checks,
in this order:

1. the module is imported (`LookupError`), as for transitions;
2. `require(read)` (`NotFound`/`Forbidden`);
3. a Prohibition of `modify` (`Forbidden`, DEC-4);
4. the version (`Conflict`, DEC-10), which hides what follows;
5. each principal is an absolute IRI (`InvalidBody`);
6. the workflow: none, `InvalidBody`; not assignable and `principals` not empty, `InvalidBody`
   (DEC-3);
7. `added = new − stored`, `removed = stored − new`; both empty: return the version held, store
   nothing (spec: equal set);
8. the authority (DEC-4): `may(modify)`; or `added == {}` and `removed == {caller}` (any
   assignee drops itself); or `added == {caller}`, `removed == {}` and the caller holds a role
   on an edge whose `from_state` is the current state, read with `_current` (the initial state
   when none is stored, `transitions.py` l.253), roles by `AccessRules.roles`; else `Forbidden`;
9. each principal in `added` may read `iri` (D-4); the first that may not, `InvalidBody` naming it
   (DEC-6);
10. one transaction: `_allow_assignees`, `replace_graph` with the new `rp:assignedTo` triples,
    activity the `Assignment` record (`assigned_principals = added`,
    `released_principals = removed`), as `Transitions._store` does.

`assignments(iri)` is `Transitions.transitions` with `v.ASSIGNMENT` in place of `v.TRANSITION`:
the same read check, the same "no longer stored" refusal, oldest first. The shared code moves,
not copied, into a new module `rdf_persistence/collaboration/services/aggregate_activities.py`:
`activities_about(session, mapper, activity_class, type_iri, iri)` (the body of
`Transitions.transitions` after its read check, l.137-146, with `_decode`) and `_about`
(`transitions.py` l.244). It joins the `discussion | … | workflows` layer of the
`collaboration-layers` contract (`.importlinter` l.173); `transitions.py` and `assignments.py`
call it.

### D-4

**May an assignee read?** `Assignments` takes `access_of: Callable[[str], Awaitable[CallerAccess]]`,
which the kit wires as `load_caller_access` bound to the store, the system database and the tenant.
For each added principal other than the caller: `rules.may(VerifiedCaller(principal=p,
global_roles=[]), await access_of(p), iri, Action.READ)`; no global role counts (DEC-6,
Rabbit-holes). The caller adding itself has already passed step 2 with its own token and access,
so it is not checked again. One query per added principal; a call adds few. The release (D-6)
builds the same test from the whole record, with no query: a `CallerAccess(tenant, state,
grants, prohibitions)` taken from the `TenantAccess` that `Tenancy.get` returns
(`tenancy.py` l.692), since `may` keeps only the rules naming the principal it is given.

### D-5

**The clearing edge.** In `Transitions._store`: when `edge.clears_assignees` and the stored root
holds assignees, `_moved` also drops the `rp:assignedTo` triples, the transaction calls
`_allow_assignees(iri, set())`, and the record gets `released_principals` (sorted). `_store`
receives the edge it already computed. The load check (spec: a clearing edge on a workflow that is
not assignable) goes in `load_workflow`, beside the other refusals.

### D-6

**The release** (DEC-7). `Assignments.release_unreadable(record: CallerAccess)` takes the tenant's
whole access record (every principal's grants and prohibitions, read once with
`Tenancy.get(tenant)` and converted as D-4 says):

1. the roots holding `rp:assignedTo`, found with `Session.graphs_with(v.WORKFLOW_ASSIGNEES)`
   (`session.py` l.838), kept only when their types map to a workflow (`Workflows.of_types`);
   assignable or not, since assignees stored while a workflow was assignable are released too;
2. per root, `kept` = its principals who may read it by `record` (D-4's test, no query);
3. per root where `kept` differs: re-read the graph and its version, then the same transaction as
   D-3 step 10 with `released_principals` = the dropped ones, the agent the caller who replaced the
   grants. A `Conflict` re-reads and tries once more. Any other refusal (a consumer's validator or
   write guard), or a second `Conflict`, logs a warning naming the root and the reason, and the
   release goes on with the next root.

`ServiceKit.release_assignees(tenant, caller)` (`rdf_persistence/api/entrypoints/kit.py`,
`ServiceKit` l.112) opens the tenant's session as `caller` and calls it.
`TenantApi.set_grants` calls it after `tenancy.set_grants` returns; any exception it raises is
logged as a warning and the route answers as before (the grants changed; spec: the release does
not undo them). Recomputing every assignment each time makes it idempotent: an interrupted release
is finished by the next grant change.

### D-7

**The queue listing.** A test first: `?assigned_to=<p2>` on books. The listing's equality filter
on a multivalued IRI slot is a triple pattern (`rdf_persistence/persistence/services/listing.py`
l.272-278), which matches any value, so no code change is planned. If T15 is red anyway, the
builder stops and the lead takes it to the developer: it would be a listing defect, outside this
EPIC's appetite.

### D-8

**Fixtures.** The shared `review.workflow.yaml` and `library_roles.yaml` stay as they are: adding
`reviewer` to them breaks two tests that append their own `reviewer`
(`tests/unit/access/test_access_annotate.py` l.13, l.22;
`tests/unit/collaboration/test_collaboration_discussion.py` l.89), and leaving it out makes the
workflow refuse an edge role it does not define (`workflows.py` l.263-267). The new tests build
their own: an assignable variant of the review workflow (`assignable: true`, `reviewer` beside
`librarian` on `in_review` → `accepted`, `clears_assignees: true` there) and a roles file that
adds `reviewer` (tenant level, `read`, `annotate`), written into `tmp_path` by a fixture in
`test_collaboration_assignees.py`, as `tests/unit/api/test_service_kit.py` l.337 does. The
refusal tests use the unchanged review workflow, which is not assignable.

## Algorithm / approach

Worked example (stage 1): book b in `in_review`, stored assignees `{p1}`, caller r granted
`reviewer` (no `modify`); `assign(b, {p1, r}, if_version=v3)`. Steps 1 to 5 pass; the workflow is
assignable; `added = {r}`, `removed = {}`; r may not modify, but `added ∪ removed == {r}` and r holds
`reviewer` on `in_review → accepted`; r may read b; one transaction writes `b rp:assignedTo p1, r`
with the activity `Assignment(used_resource=b, assigned_principals=[r])`; returns v4. Then a
librarian moves b to `accepted`: that edge clears, so b holds no `rp:assignedTo` and the
`Transition` names `released_principals = [p1, r]`.

Worked example (stage 2): p1 holds only a tenant `reader` grant; b holds `{p1, p2}`. An
administrator replaces the grants without p1's. The route answers 200 with the new grants; then
the release reads the record, finds `(b, p1)` and `(b, p2)`, p1 may no longer read b, so one
transaction writes `b rp:assignedTo p2` with `Assignment(released_principals=[p1])`, agent the
administrator.

Idempotency: `assign` with the stored set stores nothing; the release recomputes from the current
grants and assignments, so running it twice changes nothing the second time. `assign` itself is
guarded by `if_version`, so a retried call after success is a `Conflict`, not a double change.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Name the slot `assignee` | `assigned_to` (DEC-1) | `assignee` is `odrl:assignee` in `rp_access`; one schema, one name |
| Check the assignees in the router | In `Assignments` and the guard | sessions and consumers' code bypass the router |
| A second `root_values` query in the guard | Read the assignees in the existing one | every replace of a workflowed root pays it |
| Release inside `Tenancy.set_grants` | Call it from the API layer (D-6) | tenancy sits below collaboration (`.importlinter`) |
| Copy `transitions()` into `assignments()` | One shared private helper (D-3) | two copies of the provenance read drift |
| Resolve a principal's token to check its roles | Stored grants only (D-4) | the toolkit has no token for another principal |
| Hand-edit generated classes | Change `rp_workflow.yaml`, `make generate` | LinkML is the single source (AGENTS.md 2) |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A plain write adds, drops or changes an assignee | D-2 guard | `Forbidden`, nothing stored |
| An add names an assignee | D-2 guard | `Forbidden` |
| `assign` on an aggregate under no workflow | D-3 step 6 | `InvalidBody` |
| `assign` of a non-empty set under a workflow not assignable | D-3 step 6 | `InvalidBody` |
| A principal that is not an absolute IRI | D-3 step 5 | `InvalidBody` naming it |
| Stale `if_version` | D-3 step 4 | `Conflict`, after the read and Prohibition checks, before every other refusal |
| Caller without `modify` changes someone else | D-3 step 8 | `Forbidden` |
| Caller without `modify` and no role on a leaving edge takes it | D-3 step 8 | `Forbidden` |
| Prohibition of `modify` on the caller | D-3 step 3 | `Forbidden`, self-assignment included |
| An added principal may not read | D-3 step 9 | `InvalidBody` naming it |
| An added principal reads only through a global role | D-4 | `InvalidBody` (RISK-3) |
| Same set as stored | D-3 step 7 | version held returned, nothing stored, no record |
| A workflow file with a clearing edge but not assignable | `load_workflow` | refused at start-up, naming the file and edge |
| The workflow stops being assignable while assignees are stored | D-2: omitted are kept | kept and readable; `assign(iri, [])` or a release clears them |
| The release fails after the grants changed (store down, crash) | exception in `release_assignees` | warning logged, route answers 200; the next grant change finishes it (RISK-1) |
| A concurrent write during the release | `Conflict` on one root | re-read, retry once, then a warning naming the root; others go on |
| A consumer's validator or guard refuses the release of one root | any refusal raised by the commit | warning naming the root and reason; others go on; the next grant change tries again |
| A root of no workflow class holds `rp:assignedTo` | `of_types` finds no workflow | the release leaves it (the application's) |
| A replace gives a workflow class to a root holding assignees | D-2 guard | `Forbidden` (`TAKES_A_CLASS_ASSIGNED`) |
| An assignee in a state no edge leaves, without `modify` | D-3 step 8 | may still remove itself |
| A caller adds itself while holding an edge role only through its token | D-3 step 8 (`roles` counts system token roles) | allowed; step 9 skips the caller (D-4) |
| A tenant restored from a dump: assignees of the source tenant, few grants | not detected | kept until the first grant change on the new tenant releases them |
| Grants changed by a migration or a direct `Tenancy.set_grants` | not detected | no release (RISK-2); documented; the consumer may call `ServiceKit.release_assignees` |
| An aggregate deleted after assignment | `heads` empty | `assignments(iri)` `NotFound`; records kept in provenance |
| Assignee filter on a type with no `assigned_to` | listing slot check | the listing's existing unknown-slot answer (400) |

## Risks / Trade-offs

All accepted by the developer (2026-11-27, `inputs/qa.md` Q12 to Q14).

- **RISK-1** The release is not atomic with the grant change. Likelihood low (a crash or the store
  going down between two requests); impact low (an assignee who cannot open the work stays named
  on it). Mitigation: the idempotent full recomputation (D-6) finishes it on the next grant
  change.
- **RISK-2** Grant changes outside the route (a migration's `grant_roles`, a direct
  `Tenancy.set_grants`) release nothing. Likelihood medium, impact low. Mitigation: documented in
  `access.adoc`; `ServiceKit.release_assignees` is public so the consumer can call it.
- **RISK-3** A principal that reads only through a global token role cannot be assigned.
  Likelihood low (system roles are for operators), impact low. Accepted and documented.
- **RISK-4** A grant change on a tenant with many assignments costs one `SELECT` and one commit
  per released root, inside the request. Accepted; the ceiling is the request time, and the upgrade
  path is running the release on the message bus after the grant commit.
- **RISK-5** `fine-grained-access` may change how `read` is decided. D-4 calls `AccessRules.may`,
  so the assignee check follows whatever that EPIC decides.
- **RISK-6** `assign` races a grant change: the assignee is checked under the old grants, the
  release scans before the assignment commits, and the assignee stays without access until the
  next grant change. Likelihood low, impact low; accepted with RISK-1.
- **RISK-7** Each assignment and each release is a commit: it changes the version, `modified` and
  `contributor` (`session.py` l.1496-1501). A grant change that releases many roots gives a
  `Conflict` to anyone editing them at the time. Accepted: it is what a transition does too.

## Open Questions

None. (The two the planner settled without asking are recorded as decisions here: D-4, stored
grants only; D-6, the release is called from the API layer. Both are named in the hand-over to the
developer.)

## Tests

Test first, per stage. Files: `tests/unit/collaboration/test_collaboration_assignees.py` (new,
unit, the toy service in memory as `test_collaboration_workflow.py` does),
`tests/unit/collaboration/test_workflows.py` (load), `tests/unit/api/` (route + release),
`tests/feature/assignees.feature` with `test_assignees.py` (HTTP, BDD). No adapter changes, so
no new container test; `make test-containers` still runs once per stage (the release `SELECT` on
Fuseki goes through the existing store).

| Id | Requirement / scenario | Tier, file |
|---|---|---|
| T1 | a clearing edge on a workflow that is not assignable; `assignable` absent is false | unit, `test_workflows.py` |
| T2 | a new book has no assignee; an add that names one is refused | unit, `test_collaboration_assignees.py` |
| T3 | a plain write cannot reassign; a replace that omits them keeps them; same set passes | unit, same |
| T4 | an editor assigns two people; the record names both as added | unit, same |
| T5 | a reviewer takes the work, then drops it; an assignee drops finished work (no edge leaves); unassign-all and a clearing edge leave no assignee (the omitted-vs-empty case) | unit, same |
| T6 | a reviewer cannot assign someone else; a reader without an edge role cannot take it | unit, same |
| T7 | a stale version conflicts first, even for a caller who would be refused | unit, same |
| T8 | a workflow that is not assignable refuses `{p1}`, accepts `{}` | unit, same |
| T9 | an outsider is refused, named; a global-role-only principal is refused | unit, same |
| T10 | a Prohibition of `modify` blocks self-assignment | unit, same |
| T11 | same set: no record, version held | unit, same |
| T12 | acceptance releases the reviewer; a non-clearing edge keeps them | unit, same |
| T13 | the history of an assignment, oldest first; kept after delete, `NotFound` for the deleted aggregate | unit, same |
| T14 | a member leaves; access kept another way; run twice changes nothing; a failing release still answers 200; one refused root does not stop the others; a root of no workflow class is left alone | unit, `tests/unit/api/test_assignee_release.py` |
| T15 | my work: `?assigned_to=<p2>` | feature, `assignees.feature` |
| T16 | a member leaves, end to end through `PUT …/grants` then a read | feature, `assignees.feature` |

No existing test is moved or rewritten. One test double gains a keyword (D-2), and the model
snapshot `tests/fixtures/model-shape.yaml` is refreshed after `make generate` (task 1.1); every
lane that ran them still runs them and they prove what they proved.

## Delivery decisions

- **D-9** (developer, 2026-11-27): the adversarial tester runs at stage 1's Challenge, on the
  guard (D-2) and the authority rules (D-3 step 8). The developer granted the lead commit, push,
  PR and merge on green CI for this EPIC.
- **D-10** (lead, 2026-11-27): the D-8 test fixtures live in one shared helper,
  `tests/unit/collaboration/assignees_world.py`, not inside `test_collaboration_assignees.py`, so
  the builders of tasks 1.5, 1.6 and 1.8 reuse them. Stage 1 runs in this order: 1.1 (lead);
  then 1.2 + 1.4 + 1.5 (one builder: `workflows.py`, `session.py`) beside 1.7 (one builder:
  `transitions.py`, the new helper module), which touch no file in common; then 1.6; then 1.8,
  which needs `assign` to set up its assignees.
- **D-11** (lead, 2026-11-27): task 1.7 is cut in two. The extraction of the shared helper runs in
  the first wave; `assignments(iri)` and T13 move to task 1.6, since they need `assign` to have
  something to list.
- **D-12** (lead, 2026-11-27): task 1.1 was made and committed in the main checkout, against
  P-0017. Its commits were on the change's branch, so nothing moved: the main checkout went back
  to `develop` and the work continues in `.worktrees/workflow-assignees`. The re-index failed at
  stage start; the clean rebuild runs in the background and the first briefs carry impact read
  from the code, as the stage loop allows.
- **D-13** (lead, 2026-11-27, amends D-3): `aggregate_activities` gets its own layer line in the
  `collaboration-layers` contract, between `transitions | …` and `discussion | …`, not a place on
  the `discussion` line: it imports `moment_of` from `discussion`, and modules joined by `|` may
  not import each other. Moving `moment_of` was the alternative; it touches a file no task needs.
- **D-14** (developer, 2026-11-27): stage 1 merges with `gh pr merge --admin` once the local
  full gates (`make check-all`, `make test-containers`) pass, their result pasted in the PR body
  (R-0001).
- **D-15** (lead, 2026-11-27): two slips against the test conventions, recorded. The lead ran a
  whole test folder by hand (`uv run pytest tests/unit/persistence`) as a "narrow" check, outside
  the queue; and briefed the first builders before the worktree's seed had finished, so one
  task gate fell back to the full `test-fast` and hit the background limit. From here the lead
  runs only queued make lanes, and briefs builders only after the seed's notice.
- **D-17** (lead, 2026-11-28): each stage of this EPIC is reviewed with one run of lenses L2 and L3
  together, and the full review (L1, L2, L3 single; L4+L5 as one) runs once after the last stage.
  This applies the repository's rule P-0005 and `develop/agents.adoc#challenge`, which override
  `epic-delivery`'s MEDIUM default of two grouped runs in this repository.
- **D-18** (lead, 2026-11-28, accepted finding F1 of stage 1, re-labelled Critical: input
  validation at a trust boundary): `assign` accepts a principal with a space or `<>`, which then
  fails in the store as `SparqlError` (a 500 at a consumer's route) instead of `InvalidBody` as the
  error matrix says (reviewer L2+L3 #11, tester `test_a_principal_that_cannot_be_an_iri_is_refused`).
  Fix: one shared absolute-IRI check, holding `FORBIDDEN_IRI_CHARS`, in
  `rdf_persistence/core/domain/sparql.py`, used by `workflows.py` (its identifier check) and
  `assignments.py` (D-3 step 5). The developer saw the CRITICAL GitNexus rating of the stage
  (blast radius of the write path, 53 flows) and said proceed.
- **D-19** (lead, 2026-11-28): the other 15 findings of the stage-1 review are under the floor
  (listed in PR #443). Three are spine upkeep the lead carries: the error-matrix row of
  `TAKES_A_CLASS_ASSIGNED` (amended below), and `architecture/data-flows.adoc` and an `rp-messages`
  spec delta for the two new toolkit-filled slots, both added to task 2.4.
- **D-20** (developer asked for parallel work, 2026-11-28): stage 2 starts before stage 1 has
  merged, on `feat/assignee-release` stacked on stage 1's head (`378ca201`), in
  `.worktrees/assignee-release`. It takes stage 1's merge of `develop` (D-21) by a merge of
  `feat/workflow-assignees`, then is brought up to `develop` again once #443 merges. Order
  inside the stage: the docs (2.4) at once (no seed needed); after the seed, the release (2.1,
  2.2: `assignments.py`, `kit.py`, `router.py`, `tests/unit/api/`) beside the queue listing (2.3:
  `tests/feature/assignees.feature` with T15); then T16 in that feature file. Impact on
  `TenantApi.set_grants`: LOW (one caller, the route).
- **D-21** (lead, 2026-11-28, amends P-0002 for this stage): `develop` gained two epics
  (aggregate composition, dependent aggregates) while stage 1 was in review, and a rebase
  conflicted on generated files in several of this branch's commits. `develop` is merged into the
  branch once instead: the three source conflicts kept both sides (`session.py`'s transaction
  fields; `NAMES` 160 + `Assignment` = 161; both blocks of scenario-map rows), and every
  generated file and snapshot was regenerated from the sources (P-0003). The full gates run again
  on the merge, `make test-containers` included, since `develop` changed the persistence layer.
- **D-22** (lead, 2026-11-28): the release builder (2.1, 2.2) wrote the code before its tests, against
  R-0003; its eight tests passed at once, and "a member leaves" fails without the release, so
  they are kept. Its task gate (exit 0) reported no test count, and the listing builder's (2.3)
  hit its 900 s background limit: T1 and T2, the lead runs the stage's task gate once on both.
  T15 was green with no production change, as D-7 expected. The T16 builder's task gate, run
  over every stage-2 change uncommitted on 33ac4c47, exited 0 with 10987 passed and 5 xfailed;
  it stands as that re-run.
- **D-16** (lead, 2026-11-27): the worktree was installed with a bare `uv sync`, without the
  extras `make install` adds (`--all-extras`); the API tests failed for a missing module and both
  first task gates fell back to the full lane and timed out. Reinstalled with `make install` and
  re-seeded; the lead re-runs the task gate once over 1.2, 1.4, 1.5 and 1.7 (T1). Builder A also
  ran two whole folders unqueued with `-n 4`, against the guards: T1, noted, its work kept since
  the lead's gate run decides.
