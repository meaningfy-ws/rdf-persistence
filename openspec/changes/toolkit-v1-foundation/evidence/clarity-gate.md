<!-- Evidence for EPIC toolkit-v1-foundation: the clarity gate on the PLAN (design.md + tasks.md). -->

# Clarity gate on the PLAN

Each round was scored by a fresh reviewer with the full `clarity-gate` procedure (13-item checklist,
6-criterion rubric; pass mark 9/10). The gaps of each round were closed before the next one.

| Round | Score | Main gaps closed after the round |
|---|---|---|
| 1 | 7.0 | tenant resolution, version-token race, IRI minting, token verification's layer, access data storage, scenario map |
| 2 | 7.9 | role matrix, JWT access tokens and scopes, coverage and markers, generator packaging, config keys, names, one grant model |
| 3 | 8.7 | matrix and algorithm agree, test kit as package data, grant levels, scenarios mapped to tasks that can prove them |
| 4 | 8.5 | `Principal` in `rp_core`, one `label` slot, grant uniqueness, tenancy test markers, access record graph, route payloads |
| 5 | 8.8 | `RoleDefinition` shape, `install_service` with problem handlers and start-up, collections, marker hook |
| 6 | **9.1 (pass)** | all 13 items pass; ten minor gaps closed afterwards (role as a string, file port in stage 2, verifier and identity constructors, tenant root, session levels, access-record ETag, anchors, unit coverage, check order) |
| 7 | 8.1 | after the stage 0 review and the single-source amendment (PD-22 to PD-28): `--check` defined twice, manifest, plugin, case table, snapshot and guard formats, shapes for declared rules, task order |
| 8 | 8.5 | three toolkit schemas need `[[tool.rp-generate]]` entries, `rp_service.yaml` placement, `--check` without the extra, request bodies as generated classes, `load_schema` moved to `services` |
| 9 | 8.7 | aggregate bodies stay JSON-LD, `rp_service.yaml` imports, nested output folders, installed-package paths in manifests |
| 10 | 8.9 | a run hashed its own generated output as an input; tenant-root bodies; manifest wording |

The PLAN was ready for implementation from task 0.1 after round 6; rounds 7 onward re-gate the
amendments made during stage 0.
