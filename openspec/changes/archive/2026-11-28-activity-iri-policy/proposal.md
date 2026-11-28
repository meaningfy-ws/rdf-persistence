<!-- Parents: GitHub issue #197 (inputs/seed.md), the living capabilities rp-iri-policy and
     rp-messages, and the archived changes 2026-11-08-iri-policy (the policy, its fixed record) and
     2026-11-15-message-bus (activities, PD-3 urn:uuid ids, PD-8 Served). -->

# EPIC: Mint provenance activity IRIs through the IRI policy

**Golden-thread parents:** issue #197 (a consumer's URI policy needs every stored IRI under its
base); `rp-iri-policy` "Each kind of IRI follows its configured template"; `rp-messages` "Every
commit records one activity with its PROV events"; message-bus PD-3 (activity ids are `urn:uuid:`).

## Appetite

**SMALL.** One capability (the IRI policy) gains one template; the session, the event stream and
the docs are touched where they meet activity IRIs. One stage, one pull request.

## Why

Every IRI the toolkit mints for a tenant follows the configured IRI policy except one: the
`prov:Activity` each commit writes to `<tenant>/provenance` is always `urn:uuid:<uuid>`. An
application whose policy requires every stored IRI to sit under its base (portable project data)
cannot meet it, and only the toolkit mints these IRIs. Since 0.3.0 every commit writes one.

## Solution outline

The IRI policy gets an `activity_template`, defaulting to today's form, so a deployment that sets
nothing sees no change. Commands keep being built as they are today, with a fresh `urn:uuid:` id;
the session that commits one places its activity under the policy, keeping the UUID, so the stored
record, what observers, the relay and `on_commit` receive, transitions, comments and `Last-Event-ID`
all use the policy's IRI. The template joins the fixed policy record, so a deployment refuses to
start under a changed one. `Iris` refuses an activity template that would collide with another IRI
of a tenant or could not move with a restored tenant.

## Key decisions

- **DEC-1**: `IriPolicy.activity_template`, default `urn:uuid:{id}`. Variables: `{base}`,
  `{deployment}`, `{tenant}`, `{tenant_id}`, `{id}`; it ends in `{id}`, which is always the
  activity's UUIDv4 in canonical form, never drawn by the `object_id` spec. — The default then
  writes today's IRI literally; a UUID keeps every activity unique with no clash check on a write
  path that runs on every commit. Rejected: `{id}` drawn by `object_id` (short ids need a clash
  re-draw the session cannot do inside one update request). The issue's example
  `{base}{tenant}/activity/{id}` is written `{tenant}/activity/{id}` here (`{tenant}` is already a
  full IRI); `{base}{tenant_id}/activity/{id}` is allowed too. A non-default template holds
  `{tenant}` or `{tenant_id}`, so a restore moves its activities (owner decided OPEN-5, 2026-11-25).
- **DEC-2**: placement at the commit. A command still gets a provisional `urn:uuid:<u>` id
  (`command()`, `new_activity_id()` and `Served` unchanged); the session's transaction records its
  activity as the policy's IRI for its tenant with the same `<u>`. `Session.activity_iri(id)` gives
  that IRI to a handler that must store it. — No public signature changes and a consumer opts in by
  settings alone. Rejected: tenant-aware minting in `command()` and every caller (breaks the public
  `command(cls, **slots)` and every consumer handler). Owner decided OPEN-1, 2026-11-25.
- **DEC-3**: the template is part of the recorded policy and of a dump's manifest; a record or a
  manifest without it reads as the default (as `application_template` does), and a changed one
  refuses start-up or restore naming `activity_template`.
- **DEC-4**: an activity IRI is never another IRI of its tenant. Building `Iris` refuses, with
  `InvalidIri`, an activity template whose IRI for a tenant is no absolute IRI or names the tenant
  id outside `{base}` (a restore could not move it); holding the tenant and a closing UUID, it
  cannot equal the tenant or one of its graphs. An IRI the activity template mints for a tenant is never accepted as
  an aggregate or a loaded graph of it (an aggregate template with `{rp_path}` reads any segment, so
  `{tenant}/activity/{id}` would otherwise read as an aggregate). Installing the service refuses a
  schema whose aggregate root of either database would be minted inside the activity template (a
  root whose `rp_path` is `activity` under `{tenant}/activity/{id}`, with UUID object ids).
- **DEC-5**: the default template's literal words (`urn`, `uuid`) do not join the reserved id words,
  so the default policy reserves exactly what it reserves today; a non-default activity template's
  words join them like any other template's.
- **DEC-6**: under a policy, `Last-Event-ID` is accepted when it is an activity IRI the policy mints
  for the followed tenant; anything else resets the stream, as an unknown id does today.

## Rabbit-holes

- Re-identifying activities already stored: a policy is fixed once a deployment has data, so a
  deployment with `urn:uuid:` records keeps them; there is no migration to write.
- Rewriting `Served` in place: the placed IRI is computed per transaction; the `Served` (spent once)
  stays as given, so a refused-before-send commit can serve it in another session.
- Every literal `urn:uuid:` in the tests: under the default policy they stay valid and stay as they
  are.

## No-gos

- No migration of stored activities, and no way to change the activity template of a deployment
  with data.
- No change to `command()`, `new_activity_id()`, `is_activity_id()` or `Served`'s signatures or
  checks; no new id spec.
- Commit markers (`CommitMarker`, dropped by their own transaction) keep `urn:uuid:`.
- No consumer-side check of its URI policy; that is the consumer's.

---

## What Changes

- `IriPolicy` gains `activity_template` (LinkML schema, regenerated models, OpenAPI component,
  TypeScript type).
- `Iris` gains `activity(tenant, uuid)`, `is_activity(tenant, iri)` and `activity_uuid(iri)`, and
  refuses the policies of DEC-4 when built; an activity IRI is no aggregate or loaded graph
  (PD-3b), and a schema root minted inside the activity template is refused (PD-3c, also when the
  kit starts).
- The session records each activity under the policy (DEC-2); `Session.activity_iri(id)` is new.
- The event stream checks `Last-Event-ID` with the policy (DEC-6).
- The start-up guard and the dump manifest check name `activity_template` when it changed (DEC-3).
- Docs: `user-manual/iri-policy.adoc`, `howto/event-driven.adoc`, the docstrings of `Served`,
  `Mapper.served` and `messagebus.command`. The public API partial lists top-level names only, so
  the `Iris` methods and `Session.activity_iri` are named in the user manual instead (D-2); the
  partial was only regenerated.

Delivered in one PR (stage 1), as shaped; nothing the shape promised was dropped.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-iri-policy`: activities have a template (default unchanged), checked when `Iris` is built,
  fixed with the policy.
- `rp-messages`: an activity's IRI is the policy's, not always `urn:uuid:`.

## Impact

`rdf_persistence/model/technical/iris/rp_iris_services.yaml` and its generated packages;
`iris/services/iris.py`; `persistence/services/session.py` (`Transaction`);
`provenance/services/provenance.py` (`completed` takes the activity IRI);
`events/services/event_stream.py` and `api/entrypoints/sse.py`; as built, also
`iris/domain/layout.py` (the glue patterns moved from `tenancy/services/tenant_move.py`, PD-3a),
`schema/services/schema_structure.py` and `api/entrypoints/kit.py` (PD-3c),
`persistence/services/mapper.py`, `messaging/services/messagebus.py` and
`tenancy/services/tenant_dump.py` (docstrings and comments); docs. No consumer code changes under
the default policy. Serves: issue #197.
