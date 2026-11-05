# Developer answers to the remaining open questions — 2026-11-03, round 2

Seed input, preserved verbatim (typos included). Answers to the seven points still open after
`developer-answers-2026-11-03.md` (task 7.5). Recorded as DEC-26…DEC-32 in `../proposal.md`;
projected in `../architecture/candidate-adrs.md` and
`docs/modules/ROOT/pages/architecture/soa/decisions.adoc`.

The questions, as asked:

1. Triple-level access control: allow a thin in-house evaluator (DEC-8 forbids one), use
   GraphDB's FGAC and accept its licence, or both.
2. API style: REST, GraphQL, or both.
3. Annotation sets: do they count towards the `strict` policy? (Recommended: no.)
4. Graph naming: the root's own IRI as graph name, or a graph IRI derived from it.
5. Licences: Zitadel's AGPL; rdfproxy's GPL if we borrow code.
6. Owlready2 as a build-time check.
7. Scope (ADR-01): library only, or library plus generator and service kit.

---

1. we can do bith accept graphdb licence (we are partners anyways), and we coudl implement our layer as well
2. lets support both API styles (REST is first to implement, grpahql secondary); i wonder if we can support any jsonld service as well? so the UI gets jsonld???
3. I agree with your ecommednaiton
4. I though if we use graph name and root uri being the same is easier to manage the named graph, or not? not sure (if derive a separate uri si cleaner we can, but otherwise makes sense to reuse)
5. both are acceptable, everything is fine
6. not sure we need reasoning atm
7. huge scope, a library and a generator and a service kit, so basically we set teh foundations here and then MWB2 can be impemented on top of THIS

proceed
