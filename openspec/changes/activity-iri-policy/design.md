<!-- PLAN (design half) of activity-iri-policy. PLAN = this file + tasks.md. -->

# Design: activity-iri-policy

> Derives from: EPIC `activity-iri-policy` (`proposal.md`, issue #197), DEC-1 to DEC-6.
> Builds on the archived `2026-11-08-iri-policy` and `2026-11-15-message-bus` (PD-3, PD-8).
> Codebase reading: `inputs/facts.md`. Owner questions: `inputs/qa.md` (OPEN-1, OPEN-5); this
> PLAN is complete under their recommended answers.

## Context

An activity id is minted in six places, four of which know the tenant (`inputs/facts.md`); the
public `command(cls, **slots)` and `new_activity_id()` do not. Every activity reaches the store
through one place: the session's `Transaction`, which builds it (`_completed` → `completed()`),
asks whether its IRI is taken (`_taken_activity`, `_refused_by_store`, `ID_TAKEN`) and writes it
with the command's own triples (`_record`). The `Transaction` knows its session's `Iris` and tenant
(the application IRI for the application database). That single choke point is why DEC-2 places
the IRI there.

## Goals / Non-Goals

**Goals**
- G-1: with `activity_template: "{tenant}/activity/{id}"`, every commit's activity is
  `<tenant>/activity/<uuid>`, and transitions, comments, `is_recorded`, observers, the relay,
  `on_commit` and `Last-Event-ID` resume use that IRI (issue acceptance 2).
- G-2: without the template, every activity IRI, query and test is as today (acceptance 1).
- G-3: a changed template refuses start-up naming `activity_template` (acceptance 3), and a restore
  under another one is refused the same way.
- G-4: a template that would collide or not move on restore is refused when `Iris` is built.

**Non-Goals**: the EPIC's no-gos (no migration, no signature change, commit markers unchanged).

## Decisions

- **PD-1** (DEC-1): schema. `activity_template` is a slot of `IriPolicy` in
  `rp_iris_services.yaml`, `ifabsent: string(urn:uuid:{id})`, title "Activity template", pattern
  `^urn:uuid:\{id\}$|^(?:[a-z0-9/:.-]|\{(?:base|deployment|tenant|tenant_id|id)\})*\{tenant(?:_id)?\}(?:[a-z0-9/:.-]|\{(?:base|deployment|tenant|tenant_id|id)\})*\{id\}$`:
  the default, or a template that holds `{tenant}` or `{tenant_id}` and ends in `{id}` (PD-12,
  OPEN-5). A tenant-less template such as `{base}activity/{id}` is refused here, naming
  `activity_template`. `make generate`
  regenerates the Pydantic model, the shapes, the context, the OpenAPI component and the
  TypeScript type; `make check-generated` proves they match. `IriPolicy`'s description gains the
  activity template.
- **PD-2** (DEC-1): `Iris.activity(tenant: str, activity_uuid: str) -> URIRef` fills the template
  through `_fill`, which resolves `{tenant_id}` (through `_id_of`, so `app` for the application)
  only when the template holds it: the default `urn:uuid:{id}` and `{tenant}/…` templates never
  parse the tenant IRI, so a session on a tenant IRI the policy cannot parse (the testkit's
  `FAKE_TENANT`, `…/tenants/fake`) commits as today under them; under a `{tenant_id}` template
  such a tenant raises `InvalidIri` at the commit, before anything is sent. `Iris.is_activity(tenant: str | None,
  iri: str) -> bool` (`None`: of any tenant, as `is_loaded_graph` takes it) fullmatches a pattern compiled by `_pattern` with the `id` group set to
  `_UUID_PATTERN` (not the object-id pattern) and checks `_belongs(parts, tenant)` minus the
  reserved-id test of `id` (a UUID is never a reserved word). `Iris.activity_uuid(iri) -> str`
  returns the canonical UUID of a `urn:uuid:` id or of an IRI `is_activity` accepts for some tenant;
  `ValueError` otherwise.
- **PD-3** (DEC-4), three parts:
  - a. `Iris.__init__` runs `_require_activity_apart()` beside `_require_distinct_graphs`, probing
    with `_probe_tenant()` and the application IRI and the UUID
    `00000000-0000-4000-8000-000000000000`: refuse when the probe IRI has no scheme
    (`^[a-z][a-z0-9+.-]*:`), or contains the probe tenant id while not starting with
    `settings.base`. The error names `activity_template` and the reason. No equality check with
    the tenant, application, access, meta, registry or provenance IRI is written: once PD-1
    requires the tenant and a closing `{id}` (a UUID), an activity IRI always holds the tenant and
    one more UUID, which none of those IRIs can, so such a check could not be tested.
  - b. `is_aggregate(tenant, iri)` and `is_loaded_graph(tenant, iri)` answer false when
    `is_activity(tenant, iri)` (tenant `None`: any tenant the activity pattern reads). Under the
    default template no `http(s)` IRI is an activity, so their answers are today's.
  - c. `Iris.require_roots_apart(roots: Iterable[tuple[str, str]])`, roots as (`{type}`,
    `rp_path`) of the concrete aggregate roots of both databases (a new
    `schema_structure.root_paths(view)` beside `iri_types`), mints for each a probe aggregate with
    the probe UUID when the object id spec is `uuid4` (random ids never read as a UUID: hyphens,
    length) and refuses with `InvalidIri` naming the class's type and `activity_template` when
    `is_activity` accepts it. The kit calls it right after building its `Iris` (`kit.py`, where
    `Iris(settings, *iri_types(view), …)` is built).
- **PD-4** (DEC-5): `_reserved` skips `activity_template` when its effective value equals the
  default `urn:uuid:{id}`; otherwise its literal words join, like every template's.
- **PD-5** (DEC-2): the `Transaction` computes `self._activity_iri = iris.activity(tenant, uuid)`
  lazily, only when an activity is built: in `_completed`, after its early return for a session
  that neither records activities nor has a hook (so a system-database session never computes
  it). The testkit's `fake_session` records activities by default, so it does compute it; PD-2 is
  what keeps it unchanged under the default template. `uuid` is
  `Iris.activity_uuid(served.activity.id)` when a command is served, else a fresh `uuid4()`; it is
  computed once per transaction and kept. `completed()` gains a keyword `activity_id: str` and
  sets the base activity's id to it first (the standard class built with it, or
  `served.activity.replaced(id=activity_id)`), before the `Generation` and `Invalidation` parts
  are built, so each part's `activity` is `activity_id`; `new_activity_id()` is no longer called
  there. `_taken_activity` (which already returns early without a served command or recording)
  and `ID_TAKEN` use `self._activity_iri`, computed through the same lazy accessor. `_record` maps the served command's IRI to `self._activity_iri` in the
  subject and object of its own triples before skolemising. The `Served` is not changed (its
  `claim()` still spends it).
- **PD-6** (DEC-2): `Session.activity_iri(command_id: str) -> str` returns
  `str(iris.activity(tenant, Iris.activity_uuid(command_id)))`: what the commit serving that command
  will record. `ValueError` for an id that is neither `urn:uuid:` nor a placed IRI of the tenant.
- **PD-7** (DEC-6): `event_stream` gains a keyword `is_activity: Callable[[str], bool] =
  is_activity_id` that replaces the direct call in `_resumed` (the default keeps
  `tests/unit/events/test_event_stream.py`'s wiring as it is); `sse.py` passes `lambda text: kit.iris.is_activity(tenant, text)`
  (the kit's `Iris`). Under the default policy it accepts exactly what `is_activity_id` accepts.
- **PD-8** (DEC-3): no code in `iri_policy_guard.py` or `tenant_dump.py`: `effective_policy` fills
  the absent slot from `ifabsent`, and `policy_differences` names it. Tests prove both, and the
  comment at `tenant_dump.py:384` names the activity template beside the application one.
- **PD-9**: docs. `user-manual/iri-policy.adoc`: the template's row in the table, its variables,
  the DEC-4 refusals, "Changed in <next version>: activity IRIs"; `howto/event-driven.adoc`:
  `command()` gives a provisional `urn:uuid:` id that the commit places under the policy, and
  `Session.activity_iri`; `partials/reference/public-api.adoc`: the `Iris` methods and
  `Session.activity_iri`. The example template in every page is `{tenant}/activity/{id}`; the
  manual notes that the issue's `{base}{tenant}/…` is written `{tenant}/…` because `{tenant}` is
  a full IRI, and that `{base}{tenant_id}/activity/{id}` is allowed too (decided; was OPEN-3).
  Docstrings: `Served`'s (its `urn:uuid:` check is now the provisional command id, placed by the
  session; the restore rationale moves to the session), `Mapper.served`'s `Raises`, and
  `messagebus.command`'s ("a provisional `urn:uuid:` id"). `make check-docs` passes.
- **PD-10** (was OPEN-2; DEC-1): `{id}` is always the activity's UUIDv4; `object_id` does not
  apply, because a short id's clash would need a re-draw inside the commit's one update request.
- **PD-11** (was OPEN-4; DEC-6): under a non-default template, a `urn:uuid:` `Last-Event-ID` resets
  the stream without asking the store: a deployment with data cannot change its policy, so no such
  activity exists there.
- **PD-12** (OPEN-5, recommended answer): a non-default activity template holds `{tenant}` or
  `{tenant_id}` (PD-1), so a restore moves every activity with its tenant and the activity sits in
  the tenant's portable data, as #197 asks.

## Algorithm / approach

A commit under `activity_template: "{tenant}/activity/{id}"`, tenant
`https://ex.org/projects/p4x8k2m`:

1. A handler builds `command(ShelveBooks, used_resource=book)` → id
   `urn:uuid:7a1e1d6e-2f0b-4c57-9a52-2f2f5d1f6a10`; `mapper.served(cmd)` accepts it (unchanged).
2. `session.transaction(served=...)`: `_activity_iri` =
   `https://ex.org/projects/p4x8k2m/activity/7a1e1d6e-2f0b-4c57-9a52-2f2f5d1f6a10`.
3. The guard asks `ID_TAKEN` for that IRI; the record writes `<…/activity/7a1e…> a rp:ShelveBooks,
   prov:Activity` plus the command's own triples re-subjected to it.
4. Observers, the relay and `on_commit` receive the activity with that id; a follower resumes with
   `Last-Event-ID: https://ex.org/projects/p4x8k2m/activity/7a1e…`.

The same commit under the default policy: step 2 gives `urn:uuid:7a1e…`, the command's own id;
every later step is today's. A commit with no command: step 2 draws a fresh UUID.

Restore of that tenant to id `q9z3w1c`: `rewrite` moves `…/p4x8k2m/activity/7a1e…` to
`…/q9z3w1c/activity/7a1e…` in subject and object position alike (the template starts under the
base, PD-3), so the restored tenant's activities are its own.

Idempotency: placement is a pure function of (policy, tenant, UUID); a retried commit of the same
`Served` gets the same IRI, and the existing taken-IRI guard refuses a second record, as today.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Mint the policy IRI in `command()` or `new_activity_id()` | Place it in the `Transaction` (PD-5) | They know no tenant; changing them breaks every consumer (DEC-2) |
| Mutate the `Served`'s activity id | Compute `_activity_iri` per transaction | A `Served` refused before sending may serve another session |
| Draw `{id}` from `object_id` | Use the UUID (DEC-1) | Short ids would need a clash re-draw inside one update |
| Edit the generated `rp_iris_services.py` | Change the YAML, `make generate` | LinkML is the single source |
| Rewrite the `urn:uuid:` literals of existing tests | Leave them; add policy tests beside | They test the default, which is unchanged (G-2) |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Template without `{id}` at its end, or an unknown variable | schema pattern on `ServiceSettings` | validation error naming `activity_template` |
| Template uses `{deployment}` with no slug | `check_iri_policy` | `InvalidIri` (existing rule, now covering the new slot) |
| Tenant-less non-default template (`{base}activity/{id}`) | schema pattern on `ServiceSettings` (PD-1, PD-12) | validation error naming `activity_template`; a restore could not move such activities |
| Activity IRI read as an aggregate or loaded graph (a hand-made aggregate at `t/activity/U`) | `is_aggregate` / `is_loaded_graph` false (PD-3b) | the session's existing `InvalidIri`, nothing written |
| A schema root whose minted IRIs fall inside the activity template (`rp_path: activity` under `P`, UUID object ids) | `Iris.require_roots_apart` at kit build (PD-3c) | `InvalidIri` naming the class type and `activity_template`; the service does not start |
| A flat part template whose `{type}` equals a literal of the activity template | not detected | RISK-6 |
| Template names the tenant id outside the base (`urn:x:{tenant_id}:{id}`) | `Iris.__init__` probe (PD-3) | `InvalidIri`: a restore could not move it |
| Relative template (`activity/{tenant_id}/{id}`) | `Iris.__init__` probe, no scheme (PD-3a) | `InvalidIri` naming `activity_template` |
| A session that records no activity (system database) | `_completed` returns early | no activity IRI computed, nothing raised (PD-5) |
| A recording session on a tenant IRI the policy cannot parse (testkit `FAKE_TENANT`) under the default or a `{tenant}/…` template | `_fill` does not resolve `{tenant_id}` (PD-2) | the commit records as today |
| The same session under a `{tenant_id}` template | `_id_of` → `tenant_id_of` | `InvalidIri` before anything is sent |
| Restart with a changed template | `guard_iri_policy` | `IriPolicyChanged` naming `activity_template`; nothing minted |
| Older recorded policy or dump manifest without the slot | `effective_policy` fills the default | compares equal to the default; start or restore proceeds |
| Restore of a dump made under another activity template | `_check_manifest` | `InvalidBody` naming `activity_template` |
| A command whose id is neither `urn:uuid:` nor a placed IRI | `Served` (unchanged `ValueError`) | refused before anything is sent, as today |
| A command reused for a second commit | `Served.claim`, `ID_TAKEN` on the placed IRI | refused as today; same UUID gives the same placed IRI |
| `Last-Event-ID` that is a `urn:uuid:` under a non-default policy, or another tenant's activity IRI | `is_activity` false | `RESET`, the store is not asked |
| A handler stores `command.id` in an aggregate under a policy | not detected (consumer code) | RISK-2; `Session.activity_iri` documented |
| `Session.activity_iri` given a foreign id | `Iris.activity_uuid` | `ValueError` |

## Risks / Trade-offs

- **RISK-1** (likelihood low, impact medium): a toolkit path reads `served.activity.id` after
  placement and so uses the provisional IRI (a log line, the taken check, a relay key). Mitigation:
  task 1.4's first test commits under a non-default policy and asserts that no `urn:uuid:` IRI is in
  any graph of the tenant database and that `on_commit`, observers and `is_recorded` see the placed
  IRI; an `ast-grep` sweep for `served.activity.id` / `.activity.id` in `persistence/` is part of the
  task's acceptance.
- **RISK-2** (likelihood low, impact low): a consumer handler that wrote `command.id` into an
  aggregate, or into a slot of a later command, now writes the provisional IRI under a policy
  (placement re-subjects only the command's own IRI). Accepted: no toolkit code does it
  (`inputs/facts.md`); `Session.activity_iri` and the how-to cover it. Under the default policy
  nothing changes.
- **RISK-3** (likelihood low, impact low): logs of a bus handler show the provisional id while the
  record holds the placed one. Accepted; same UUID, and the how-to says so.
- **RISK-4** (likelihood very low, impact medium): adding the default template's words to the
  reserved ids would hide a stored tenant or object id `uuid`. Mitigated by PD-4, proved by a test.
- **RISK-5** (likelihood low, impact medium): a consumer sets the template on a deployment that
  already has data and cannot start. Intended (DEC-3); the start-up error names the field and the
  user manual says the template is chosen before the first start.

- **RISK-6** (likelihood very low, impact low): under a flat part template
  `{base}{tenant_id}/{type}/{id}`, an owned class whose `{type}` equals the activity template's
  literal segment (`activity`) mints parts whose IRIs could equal an activity's. There is no
  `is_part` to guard; accepted, and the user manual says to keep the activity segment apart from
  class types. Parts nested under `{root}` (the default) cannot collide.

## Spec deltas

`specs/rp-iri-policy/spec.md`: MODIFIED "Without a policy, IRIs are today's" (adds the activity);
ADDED "Activities follow the activity template" and "The activity template is checked".
`specs/rp-messages/spec.md`: MODIFIED "Every commit records one activity with its PROV events"
(the IRI sentence only).

## Open Questions

OPEN-1 and OPEN-5 in `inputs/qa.md`; the PLAN assumes their recommendations. OPEN-2 to OPEN-4
were decided by the planner: PD-10, PD-9, PD-11.
