<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: an LDES view over the provenance graph

## Where it comes from

The manual-revision-notes initiative (`../../manual-revision-notes/inputs/`):

- `improvements.md`, group **H**, first bullet: "**LDES view** over the provenance graph, as an
  optional, harvestable read route for EU and SEMIC consumers. Honour the specification; Python
  has no mature library to depend on (Q-4)."
- `analysis.md` §4.2 (row "LDES / TREE": never considered by the research) and §4.3 item 5 (the
  feed is push with bounded catch-up; no LDES-shaped pull feed; honour the specification, do not
  take a dependency).
- `analysis.md` §6, **Q-4**: "Add an LDES view over the provenance graph as an optional read route,
  as a separate EPIC?"
- `keep.md`, "Live event delivery over SSE": push with bounded catch-up stays; "an LDES pull view
  would be an *addition*, not a replacement".
- `answers-2026-11-17.md`: the developer's answer to Q-4, verbatim, "shape the epic, but this is
  low priority"; slicing row "later | `ldes-view` | H (Q-4) | MEDIUM, EPIC only".

This change owns **H-1 (LDES view)** and **Q-4**. Nothing else of the initiative.

## Checked while shaping (2026-11-17)

- **LDES**: SEMIC's Linked Data Event Streams specification, release **1.0.0** (9 May 2026),
  `https://w3id.org/ldes/specification` →
  `https://semiceu.github.io/LinkedDataEventStreams/releases/1.0.0/`. Terms used by this EPIC:
  `ldes:EventStream`, `ldes:timestampPath`, `ldes:versionOfPath`, `ldes:versionCreateObject`,
  `ldes:versionUpdateObject`, `ldes:versionDeleteObject`, `ldes:immutable`, `ldes:retentionPolicy`
  (none declared means the full log), `ldes:pollingInterval`.
- **TREE**: the TREE hypermedia specification, W3C Draft Community Group Report of **20 June
  2025**, `https://w3id.org/tree/specification` → `https://treecg.github.io/specification/`. Terms:
  `tree:Collection`, `tree:view`, `tree:member`, `tree:shape`, `tree:Node`, `tree:relation`,
  `tree:GreaterThanOrEqualToRelation`, `tree:LessThanRelation`, `tree:path`, `tree:value`,
  `tree:node`, `tree:remainingItems`. Member extraction defaults to the member's Concise Bounded
  Description.
- **Python libraries (P-0008, archived DEC-5 reuse bar: > 200 stars and a commit in 12 months)**:
  none. PyPI has no `ldes`, `pyldes`, `ldes-client`, `python-ldes`, `ldes-server` or `tree-ldes`;
  the GitHub search for Python LDES repositories finds demos with 1 to 3 stars. The ecosystem is
  Java (`Informatievlaanderen/VSDS-LDESServer4J`, 13 stars) and TypeScript. The analysis holds:
  honour the specification with rdflib.
- **A harvesting client to test against**: npm `ldes-client` (rdf-connect), 0.6.1, published
  2026-11-16, about 3,700 downloads a month. Usable as a test oracle in the e2e tier, not as a
  dependency of the package.

## What the code does today (checked 2026-11-17)

- Every commit records one PROV activity in the tenant database's provenance graph
  (`services/provenance.py` `completed`, `activity_triples`); its generations and invalidations are
  blank nodes naming the entity, its class and its version token; `at_time` is the activity's end,
  taken from the service's clock. Records are kept forever (`rp-messages`, "Activity records are
  kept"); a restore keeps their IRIs.
- `GET {prefix}/{tenant_segment}/{t}/rp-events` (`entrypoints/sse.py`) streams them as server-sent
  events, cut to what the caller may read (`services/visible_part.py`), with a 7-day resume window
  on `rp:relayedAt` (`services/session.py` `relayed_since`).
- There is no anonymous access: every route needs a verified caller.
