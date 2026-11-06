<!-- Seed inputs for EPIC toolkit-v1-foundation. Secondary and preserved: never groomed or deleted.
     The shaped EPIC (proposal.md) supersedes them as the primary truth. -->

# Seed brief: implementing rdf-persistence architecture v1

## Sources

- rdf-persistence architecture v1 and its revision of 2026-11-05:
  - `docs/modules/ROOT/pages/architecture/index.adoc` (needs N-1..N-11, building blocks, O-1, O-2)
  - `generation.adoc` (metamodel, revision of 2026-11-05)
  - `api.adoc`, `access-control.adoc`
  - `open-decisions.adoc`: the decisions of 2026-11-05, D-1..D-12
- Background decisions: `openspec/changes/archive/2026-11-05-soa-python-rdf-orm/proposal.md`
  (DEC-1..DEC-39; DEC-29, the graph IRI is derived from the root IRI).
- The first consumer's architecture: mapping-workbench-v2, `docs/modules/ROOT/pages/architecture/`.
  It maps its decisions and use cases to N-1..N-11. This repository uses no consumer terms.
- Spike evidence from the consumer's architecture work: mapping-workbench-v2
  `openspec/changes/architecture-v1/evidence/spike-generation.md`. Generation steps 1–4 were run
  on LinkML 1.12.1, and Fuseki 5.1.0 behaviour was checked.
- The existing scaffold: an empty `rdf_persistence/` with its layers, `tests/`, uv, import-linter,
  and the CI gates.

## The developer's words (2026-11-05), verbatim

On the metamodel and the generator:

> the metamodel presented in the model to code page, looks okay at the first site, i was wondering
> if you could include the necessary minimal ODRL concepts/model already from the getgo, and PROV-O
> ones, along with SKOS and DCT as default set of annotation models across ... everywhere;
> the linkml models must always prescribe/expect uris, labels and descriptions/definitins (this
> could be a hard checkon created app models)
> [...] the access control definitions models in linkml must always be in a separate midule from
> the domain model); in fact ACL/RBAC metamodel must live in rdf-persistence, and apps import it
> the generator must generate pydantic and type script classes, along diagrams, shapes. and jsonld
> context; but they must be placed in the prpoer place, for example python code in backend package,
> typescript in frntent package, etc ...
> we will likely have to extend the linkml generators, to handle the meta contructs in this
> architecture

On the adapters and identity:

> lets implement and serve in rdf-persisteny already the adapters and fucntionalities with fuseki,
> zitadel, and file storage (garage/minio), note that the zitadel functionality is needed in the
> frontent and backend, and a login from frontend must be graciously passed to the backend [...]
> if we will have api-based interaction then we must be able to login via the api as well

On the API:

> do we even need a "mapper" to python classes? can we somehow make the backend lighter [...] the
> api preferably must be as light as posisble to facilitate CRUD functionality+RBAC functionality
> over a generic triple store

## The decisions (2026-11-05), verbatim

> D1- yes, A and B
> D2 only for domain services
> D3 as you recommdn , yes
> D4 I like odrl that we can have own specification in RDF, but then when it comes to management
> and implementation i like that openfga already has an implementation, but perhaps we can also do
> an implementation of our own ... defer for now openfga unless there is an cheap oportunity to
> reuse, otherwise deferr
> D5 yes, one model
> D6 okay
> D7 yes
> D8 okay (but make sure the mermaid diagrams are not too large, te keep readability)
> D9 yes
> D10 yes indeed
> d11 yes (but now we do only architecture, imlementation in a separte epic)
> d12 just said, implement inside rdf-persistence repo, in a new epic that you will shape after the
> architecture is ready
> On lightweight api, lets go with A and B (the best), and keep option C as a backup future
> implementation
> on acces control go with option A as recommended
> make these updates to architecture, then shape the new epic to implement this. I think this epic
> shape shall be in the rdf-persistence project so it is implemented there
