<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: the consumer's needs

## Source

- Consumer: MWB2 (`meaningfy-ws/mapping-workbench-v2`), change `domain-model-v2` (shaping), file
  `openspec/changes/domain-model-v2/requirements/rdf-persistence.md` and its issue drafts
  `requirements/rdf-persistence-issues/01..07`.
- rdf-persistence commit locked by the consumer: `6bf3471` (2026-11-11).
- Asked for by the developer, 2026-11-12: plan the four filed issues as one toolkit change.

## The four filed issues

| Issue | Title | Consumer requirement ids |
|---|---|---|
| [#78](https://github.com/meaningfy-ws/rdf-persistence/issues/78) | List the resources that refer to a given resource (reverse references) | R-5; M-16, M-23 |
| [#79](https://github.com/meaningfy-ws/rdf-persistence/issues/79) | Reference collections: typed sets of references, by list or by rule, that never own their members | R-4; M-16, M-32 |
| [#80](https://github.com/meaningfy-ws/rdf-persistence/issues/80) | Configurable workflow states on any resource, with transitions, permissions and history | R-1; M-11, M-36, M-41 |
| [#81](https://github.com/meaningfy-ws/rdf-persistence/issues/81) | Discussion threads on any resource: comments, mentions, references, audience by role | R-2; M-11, M-41 |

What the consumer does with them (consumer terms, kept here only):

- Mapping rules go through review (under development, internal review, client review, accepted,
  change requested); technical mappings and validation findings have their own workflows (#80).
- Reviewers comment on mapping rules; editors leave notes the client must not see; comments refer
  to other rules or reports (#81).
- A project carries all its resources; packages, groupings and suites are pointer sets over them,
  by list or by rule (#79).
- Shared resources (a reusable ontology fragment used by many mapping rules) must show where they
  are used before an edit or a delete (#78).

## Deferred by the developer (2026-11-12)

Drafts 01 (named states of a tenant), 02 (diff between two states) and 03 (outputs linked to a
state) were not filed. The developer: change history in the toolkit "might be too much for now;
best if the triple store handles versioning (like Fluree)". The consumer records the version
tokens of the aggregates a run used and compares them later (its R-3, R-6; Q-35).

## Version token: checked 2026-11-12 at `develop` `e70c889`

- `Session.get_graph(iri)` returns `(graph, graph_iri, version)`; the generic API sends the
  version as `ETag`.
- `UnitOfWork.get` reads the version but keeps it in the private `_versions`; the object-level API
  a consumer uses gives no way to read it. Hence the small in-scope requirement in
  `specs/rp-aggregate-store`.
