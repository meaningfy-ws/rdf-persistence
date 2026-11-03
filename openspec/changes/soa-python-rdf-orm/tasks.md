EPIC: soa-python-rdf-orm — State of the art: Python RDF ORM, repository and RAD building blocks

# PLAN — tasks

Every ask the developer made on 2026-11-03 is an action here, traced to the decision it
implements (DEC-n in `proposal.md`). Raw inputs: `inputs/`. Status: [x] done · [~] in progress ·
[ ] to do.

## 1. Set-up

- [x] 1.1 Create the EPIC change and the SoA branch `docs/soa-python-rdf-orm`.
- [x] 1.2 Preserve the seed briefs and Confluence digests in `inputs/`.
- [x] 1.3 Scaffold the Antora docs component (`docs/`) for the results.

## 2. Candidate discovery and selection

- [x] 2.1 Short list of known Python ORM / repository libraries.
- [x] 2.2 Features, maturity, maintenance and popularity per candidate (GitHub, PyPI, npm).
- [x] 2.3 Add the Confluence "SOTA Rapid Application Development" candidates; JS-friendliness;
      semantic.works as reference (DEC-3).
- [x] 2.4 Build on mature libraries, never reinvent (rdflib, Oxigraph, SPARQL clients) (DEC-4).
- [x] 2.5 Reuse threshold: > 200 stars and a commit in the last 12 months (DEC-5).
- [x] 2.6 Include Owlready2 (ontology world) and semantic.works explicitly (DEC-6).

## 3. Deep analysis method

- [x] 3.1 Clone candidates as siblings; index every analysed library with GitNexus.
- [x] 3.2 Fetch and synthesise each library's documentation with the code findings.
- [x] 3.3 Score features, approach and patterns, developer friendliness, ease of
      implementation, data-centric / DDD orientation (rubric C1–C8).
- [x] 3.4 Run analysts in parallel, one per library group.
- [x] 3.5 Systematise features in one groomed place (feature taxonomy) and grow it per round.
- [x] 3.6 Cross-check every newly found feature across all other libraries.
- [x] 3.7 Five rounds, each adding new analysis angles across all libraries (DEC-9).
- [x] 3.8 After each round: keep raw findings per library, polish per-library pages, refresh
      one integrated findings page for system architects.

## 4. Scope extensions

- [x] 4.1 Map the whole MWBv2 chain: modelling → generated Python backend → data-management
      service → JS clients consuming JSON-LD (DEC-7). Read the five MWB Confluence pages.
- [x] 4.2 Authorization (ACL/RBAC, graph- and triple-level) surveyed, never reinvented;
      Zitadel and policy engines included; persistence stays ACL-agnostic (DEC-8).
- [x] 4.3 Building-block layers L0–L6 and several architecture variants (DEC-10).
- [x] 4.4 Coherent ecosystem, easy to use and maintain: C9 composability, C10
      maintainability (DEC-11).
- [x] 4.5 Developer-experience deep dive for every library, so we design a library developers
      love (DEC-12).
- [x] 4.6 Record for every tool what it is for and the angle it was built from (tool catalogue).
- [x] 4.7 DDD consistency boundaries: aggregates, transactions vs messages, how SQLAlchemy and
      other ORMs handle multi-object transactions, whether Unit of Work and the cosmic-python
      patterns are needed, better alternatives (DEC-13).
- [x] 4.8 Side question: property-graph / Neo4j compatibility behind the same ports (DEC-14).
- [x] 4.9 Mainstream ORM developer-experience benchmarks and an API sketch (DEC-12).
- [x] 4.10 Schema evolution, migrations, testing and operations ("day 2").

## 5. Rounds

- [x] 5.1 Round 1 — twelve libraries, taxonomy v0.
- [x] 5.2 Round 2 — cross-check v1 features; taxonomy v2.
- [x] 5.3 Round 3 — angles L0, L2/L6, L3, L4, L5; DX, seams, C9/C10; v2 cross-check.
- [x] 5.4 Round 3 harmonisation — taxonomy v3, catalogue extension, per-library and per-angle
      pages, building-block map, variants, integrated page.
- [x] 5.5 Round 4 — new angles (4.7–4.10); v3 cross-check, purpose and origin, variant fit
      for every candidate.
- [x] 5.6 Round 4 harmonisation.
- [x] 5.7 Round 5 — final cross-check, build-versus-reuse matrix per layer, risk register.
- [x] 5.8 Round 5 harmonisation and an independent review of the docs (four eyes).

## 6. Architecture analysis (Meaningfy architecting practice)

- [x] 6.1 Business context and architectural drivers from all asks and Confluence pages.
- [x] 6.2 Use-case catalogue: White (summary) and Blue (user-goal) use cases, Cockburn style.
- [x] 6.3 For each use case: how it is fulfilled, which layers and which variant, what exists
      and what is missing and must be built.
- [x] 6.4 C4 views (L1 context, L2 containers per variant, L3 for rdf-persistence) and key
      sequences (commit, authorized read, change event).
- [x] 6.5 Candidate ADRs per C4 level (options and trade-offs; decisions left to the developer).
- [x] 6.6 Diagrams as individual PlantUML `.puml` files and as Mermaid in `.md` documents.

## 7. Delivery

- [x] 7.1 `make build-docs` passes; all xrefs resolve.
- [x] 7.2 Build-versus-reuse decision support handed to the developer (decision is theirs).
- [x] 7.3 Commit on explicit consent (no AI attribution) — a756cde; PR #2, stacked on #1, retargets to `develop` once #1 merges.

## 8. Follow-ups found during the review

- [x] 8.1 Refresh the architecture analysis (`architecture/`) with the round-4 findings (DDD
      aggregate session, migrations, DX API shape) — round 5.
- [x] 8.2 Publish the architecture analysis in the Antora docs (summary page linking the `.md`
      and `.puml` sources).
- [x] 8.3 Design-implications page kept as the bridge from findings to the next EPIC's ADRs.
