# Q&A record (secondary, never groomed): shaping session 2026-11-24

Seeds: issues #300 to #312, read in full; the in-flight change `domain-values-and-fixes`
(branch `feat/domain-value-modules`), which already holds #301, #303, #302, #300; the gated,
undelivered `converter-hardening` (branch `docs/plan-converter-hardening`). Code read:
`rdf_persistence_generation/uml/slots.py` (`_shape_kwargs`, `usage_of`),
`rdf_persistence/tenancy/services/tenancy.py` (`set_grants`),
`rdf_persistence/api/entrypoints/router.py` (`set_grants`, l.316-330),
`rdf_persistence/access/services/access.py` (`validate_grants`),
`rdf_persistence/persistence/services/session.py` (`find`, `_filter`, `_text`),
`rdf_persistence/persistence/services/listing.py` (`list_request`),
`rdf_persistence/collaboration/services/workflows.py` (`state_iri`),
`rdf_persistence/__init__.py` (`_LAZY_MODULES`).

The owner's priority (verbatim order): #301, #300, #302, #304, then #303, then #305 to #312.

## Round 1 (the backlog)

| Question | Answer |
|---|---|
| The in-flight epic merges #301, #303, #302, #300 (its DEC-9); the owner's priority puts #300 and #302 before #303. Reorder? | **Keep DEC-9.** |
| Where does #304 go? | **A new bug-fix epic** (P-0020) with the other defects, #306, #311, #312. |
| How are #305 to #312 sliced? | **By concern:** fixes (#304, #306, #311, #312); guards (#305, #309); access (#307, #310); filters (#308). |
| #307: may a schema migration rewrite or drop grants naming a removed role? | **Yes, the migration may**: the toolkit gives migration steps a supported way (shaped in the access change). |

## Round 2 (this change)

| Question | Answer |
|---|---|
| #306: where does the role check live? | **Inside `Tenancy.set_grants`**; the route drops its own call. |
| #312: how far? | **`find` and the HTTP listing**: the listing gains an absence filter. The syntax was left to the planner (DEC-5). |
| #311: export or docs only? | **Export `state_iri`** lazily from the top level. |
| Risks to treat | All four: #304 changes converter output; #306 meets stored bad grants; #312 changes what `None` means; the consumer's lock drifts. |

Scenarios: each issue's own Acceptance list, plus a toy-library case (stated in round 2, not objected to).
