# Developer answers to the SoA open questions — 2026-11-03

Seed input, preserved verbatim (typos included). Answers to the open questions of
`docs/modules/ROOT/pages/architecture/soa/index.adoc` and `design-implications.adoc`.
Recorded as DEC-15…DEC-25 in `../proposal.md`; projected in `../architecture/candidate-adrs.md`
and `docs/modules/ROOT/pages/architecture/soa/decisions.adoc`.

---

let me give you some answers on thos open questions, and you will revise and project consequences n the documentation.

on ACL granularity we want to kee triple level access control, what they do in fluree, with SHACL like expressions is quite cool. how hard is it to implement or does it already exist?

on flur.ee it is cool , but we shall stay away from custom technologies and aligned to open w3c standads, hence mainly classic triple stores please; unless there is real BIG BIG value in adopting some commercial solutions.
i like graphdb, oxygraph, and the otehr ones ...

UI will never access the triplestore, only thrugh the middleware, and using REST or GraphQL APIS

conract: we no not need compatibiility with semantoc workds, but they have a few good features that are wothrt reusign or reimplementing

on generation, I am no sure whatever is mre reliable and more easy to maintain

model source, I like UML and LinkML, I like both, we could stick to LinkML for now

unit of work ... Named graph per aggregate sounds like a safe idea, and name the graph with the same uiri like the root entity of the agregate; this however puts lots of burden on managing graphs? or not necessarely? Oh! and then we could control ACL at the graph level? hmmm, but perhaps we shall still eb abel to do ACL at the triple level too

reusable threshold ... whatever is best or elegant or maintainable

cannot decide on teh design of the core now, keep options open

no real need for property graphs today

no need real time reasoning

   we shall declare teh aggregates boundaries in LinkML somehow (what are the options?)

aggregates commit policy, I think it shlal be strinct no? but keep options as configurations, not sure of the implications

version could be as mapper metadata, better, no? it is not a domain bbut orthogonal featre, like logging, or annotations or a discussion on an arbitrary object (we shall support this latter too, various sets of annotations on domian objects like discusisons, comments, provenance, etc)

on events ... I would say both ... ideally we wold use an MQ something like Redis

on typed metamodel comparison, not sure, both? what is better, more elegant?

on multi valued slots ... either is fine list and set okay

if repository is required or sesison enough, I dont know whatever is best

for now no migration generation, but .... this is an importnt aspect to kepe in mind, perhaps yes e want this fature, for max maintainability
