# Seed brief — developer, 2026-11-03 (scope extension, verbatim)

do not stop until you have one or two analysis passess continually adding new analisys angles across all the libraries.

i will want o ake a decission afterwrds what to build and what to reuse, but i need to know what xists. we want also to put the building blocks on the map, similar to mu from semantcs works, that supports also the mapping workbench2 development approach: modelling -> generate code for python backend (including ACL RBAC, ideally something with a SPARQL like laguage like in Fluree, or semantic works), and then generate a data management server/service, for the UI app, and then use classical modern js libraries handling jsonld from teh server. also ACL gnostic,

take a look at more ideas in teh mapping workbench here :
https://meaningfy.atlassian.net/wiki/spaces/MR/pages/2001109013/LinkML+evaluation
https://meaningfy.atlassian.net/wiki/spaces/MR/pages/2000945161/Flur.ee+evaluation
https://meaningfy.atlassian.net/wiki/spaces/MR/pages/2128642071/Model2OWL-LinkML+Evaluation
https://meaningfy.atlassian.net/wiki/spaces/MR/pages/2107342856/MWBv2+Developer+Runbook
https://meaningfy.atlassian.net/wiki/spaces/MR/pages/2122219644/How+do+we+code

note we must not re-invent anything around RBAC (graph level, or triple level even better), if anythign exists mut be botrrowed, including links to frameworks like zytadel

## Digest of the five Confluence pages (leader, 2026-11-03)

- **LinkML evaluation (v5, 2025-11):** accepted as the developer-friendly schema SSoT. Gaps:
  relationships and language tags unclear in instance YAML; closed-world validation; no
  rdf:type for instances (containers trick); no RDFS/OWL→LinkML path (schema-automator only);
  weak TypeScript generator (no enums, `uri`→str, dates); Pydantic `AnyUrl` not mapped;
  imports/modularity issues; linter fails on `Any` unions. gen-owl emits restrictions.
- **Flur.ee evaluation (v2, 2024-07):** accepted "with reservations". Wins: JSON(-LD)
  request/response, nested `@id` auto-join, no OPTIONAL juggling, idempotent IRI writes,
  JWT/identity-based data-centric policies, ledger time-travel. Losses: no real SPARQL 1.1
  endpoint (vendor lock-in, FlureeQL), no cascade delete, no OTM/ORM, no Python client
  (aioflureedb immature), no bulk file load, v3 closed-mode/policy docs missing, no UI.
  Open action: compare a Fluree repository vs a Fuseki/GraphDB repository; test JWT authz.
- **Model2OWL–LinkML evaluation (v2, 2024-10):** model2owl (XSLT) LinkML export needs fixes
  (enum, NCName, `String` vs `string`, no `uri` type); use `linkml:types`.
- **MWBv2 Developer Runbook (v30, 2024-10):** MDD + DDD + data-centric LDApp. UML (SEMIC
  conventions, Enterprise Architect) → model2owl + LinkML → generated, never-edited data
  classes (generated at build and test time) → Python 3.13 / FastAPI / Pydantic / rdflib
  backend with cosmic-python patterns + Unit of Work → persistence in Fluree → TS frontend
  talking near-directly to the DB through a proxy/middleware (GraphQL-like freedom, no fixed
  API contracts). Cypress + Gherkin E2E. Coverage ≥ 90 %.
- **How do we code (v9, 2024-10):** TDD task loop, Gherkin by QA, story/feature branches.

## Follow-up (developer, 2026-11-03, verbatim)

can we throw in also the ne4j compatibility? (like how easy would it be to support also property graphs, bu this is a side question, fous is on triple stores); also we wnat to know how to manage the problem of boundaries described in ddd; as there is an issue to be handle dependcies between classes, which ones go together in a transaction, and which ones can go independet in a "message" or transaction.
same is true for sparql alchey no? they somehow handle transactions across morethan a table/object;

do we need unit-of work, and otehr design patetrns from the cosmic pythn? but there may be otehr better ideas of course as well...
