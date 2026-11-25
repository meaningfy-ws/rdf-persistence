<!-- Secondary input, never groomed: the planner's codebase reading of 2026-11-22 (develop 25e23156). -->

# Facts: where activity IRIs are minted, checked and read

Re-checked 2026-11-25 against develop 12d84873 (after grant-roles, aggregate-guards, the migration
changes): every symbol, file and test file below still exists; the living `rp-iri-policy` and
`rp-messages` are unchanged. New on develop: `Iris.aggregate_id_of` (referrer naming,
`collaboration/services/referrer_naming.py` `located`) reads any `{rp_path}` segment like
`is_aggregate`, so it joins PD-3b. `WriteGuard.prepare_remove`, the transaction's read cache,
`migrate_database(grants=)` and `grant_report` mint, check or read no activity. The comment PD-8
names is still at `tenant_dump.py:384`.

## Minted

| Where | How | Knows the tenant and `Iris`? |
|---|---|---|
| `provenance/services/provenance.py` `new_activity_id()` | `urn:uuid:` + `uuid4()` (`ID_PREFIX`) | no (pure module) |
| `provenance.completed()` (no command served) | `_standard(changes)(id=new_activity_id())` | no; its caller `Transaction._completed` does |
| `messaging/services/messagebus.py` `command(cls, **slots)` | `cls(id=new_activity_id(), …)`; public, used by consumers before `bus.handle(command, collaboration)` (howto/event-driven.adoc) | no |
| `collaboration/services/transitions.py` `_store` (no command) | `Transition(id=new_activity_id(), …)` | yes (`self._iris`, the access's tenant) |
| `collaboration/services/discussion.py` `_store` (no command) | `PostComment`/`PostReply(id=new_activity_id(), …)` | yes |
| `api/services/file_removal.py` | `DeleteFile(id=new_activity_id(), …)` | yes (the tenant argument) |
| `persistence/services/session.py` `new_marker` | `CommitMarker(id=urn:uuid:…)`: a commit marker in the registry, inserted and dropped by the same transaction; never kept. Not an activity. |

## Checked

- `Served.__init__` refuses an activity id that is not `urn:uuid:` + canonical UUID (`ValueError`),
  reason in its docstring: an aggregate IRI as an activity id would be rewritten on restore; no
  unchecked text may reach an IRI (message-bus D-3).
- `Mapper.served` documents the same `ValueError`.
- `events/services/event_stream.py` `_resumed`: `is_activity_id(last_event_id)` guards the
  `Last-Event-ID` header before the store is asked (D-21); anything else is `RESET`.

## Read and used after the commit

- `Transaction._taken_activity`, `_refused_by_store`, `ID_TAKEN`: the served activity's IRI is asked
  for in the provenance graph (a reused IRI refuses the commit).
- `Transaction._record`: `activity_triples(activity, types)` plus the `Served` triples (subject: the
  command id) skolemised under the provenance graph.
- The completed activity goes to `on_commit`, the relay and the bus observers; `kit._hand_over`
  probes `session.is_recorded(activity.id)` for an incoming event.
- Transitions and comments are found by `session.activities(type, prov:used, target)`, keyed by the
  stored IRI; no aggregate graph holds an activity IRI (the comment is a root the activity names).

## The IRI policy

- `rp_iris_services.yaml` `IriPolicy`: one `*_template` slot per kind, defaults by `ifabsent`;
  `effective_policy` fills defaults and the settings' variables, so a recorded policy or a dump
  manifest without a newer template compares equal to the default (as `application_template` did).
- `iri_policy_guard.guard_iri_policy` compares the effective policies field by field and names the
  differing ones; `tenant_dump._check_manifest` does the same for a dump.
- `Iris._reserved` takes the literal words of every set template; an id equal to one is redrawn and
  never matched.
- `tenant_move.rewrite` replaces the delimited tenant id in every IRI under `{base}` (graph, subject,
  object); `glued_templates` iterates over every `*_template` field, so a new template is covered.
- The template variables available: `{base}`, `{deployment}`, `{tenant_segment}` (fixed), `{tenant}`,
  `{tenant_id}`, `{root}`, `{type}`, `{rp_path}`, `{id}`, `{issuer}`, `{sub}` by kind.

## Tests that write `urn:uuid:` literally

About 40 test lines build activities or commands with literal `urn:uuid:` ids (feature
`test_messages.py`, unit provenance, collaboration, events, api, schema; integration
`test_activity_cost.py`). Under the default policy they stay valid unchanged.
