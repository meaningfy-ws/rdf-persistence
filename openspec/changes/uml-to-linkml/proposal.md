<!-- Parents: issue #196 and its four comments (inputs/seed.md); openspec/specs/rp-generation
     ("LinkML is the single source of every model artefact"); rp-metamodel; the analysis diagram
     archive/2026-11-05-soa-python-rdf-orm/inputs/analysis/integration-diagrams/c1-uml-to-linkml.puml.
     Serves: MWB2 v2-02-model-from-ea (phase B), and through it v2-03..v2-05 (D-12).
     Seeds: inputs/seed.md, inputs/qa.md. -->

# EPIC: Generate LinkML from a UML class model (Enterprise Architect .qea)

## Appetite

**MEDIUM.** One new capability (a converter and its command) in `rdf_persistence_generation/`, with
its tests and one how-to page. Two stages: stage 1 the reader and the plain UML rules, stage 2 the
toolkit-aware rules.

## Why

Teams whose domain experts draw UML in Enterprise Architect want EA to stay the source and the
LinkML to be regenerated from it. Porting by hand is slow and drifts with every modelling round. The
first consumer has 35 tasks across `v2-02`..`v2-05` waiting for this. Nothing in that consumer moves
without it, so it comes first.

## Solution outline

`rp-uml2linkml model.qea --package <root> --prefixes prefixes.yaml --out models/ [--root-name app]
[--exclude-package <p>]… [--default-mixins Described,Tracked]` reads the `.qea` (an SQLite file,
read with stdlib `sqlite3`). It writes one `module_kind: domain` LinkML module per UML package plus
a root schema importing them, and the output passes `rp-generate`'s lint and boundary check
unchanged. It writes a report listing what it left out.

- **Stage 1, plain UML:** the rule table of the issue body: packages, classes and IRIs, abstract,
  generalisation, attributes with the XSD map and cardinality, associations, enumerations (and the
  SEMIC-style dependency), notes, «root» with `rp_path`, boundaries and composites making `owned`
  slots, "not generated" stereotypes, and shared slots with `slot_usage`. Output order is stable,
  so a second run on an unchanged model is byte-identical. An element no rule maps (an association
  class, an n-ary association) fails the run, naming the element and the missing rule, and nothing
  is written. Stage 1 also holds the spike of DEC-4.
- **Stage 2, toolkit-aware:** the rules of the four comments. The toolkit is not drawn: default
  mixins, `rp_mixins`, `workflow` giving `UnderWorkflow`, and drawn generalisations to toolkit
  classes still accepted. Toolkit slots are reused by `slot_uri`, except `id`: `dct:identifier` is
  a business identifier. Abstract parents of roots get `AggregateRoot` without `rp_path`. One slot
  is used across packages. «tenant root» becomes `graph: meta`. Excluded packages and links to them
  are reported. Untitled elements are titled. Tagged values become annotations and unique keys
  (DEC-2, DEC-3).

## Key decisions

- **DEC-1:** `.qea` only. The issue says this partial version unblocks the consumer; rejected: XMI
  2.x in this EPIC.
- **DEC-2:** a class tagged value whose name is a class annotation of the toolkit's metamodel
  becomes that annotation, its value checked against the annotation's range or enum. The converter
  reads the list from the metamodel and keeps no copy of it. This covers `rp_path`, `workflow`,
  `graph`, `rp_unlabelled`, `database` and `rp_writes` today, and `rp_on_referenced_delete`
  (`delete-refuses-referenced`) when it lands, with no change here. Rejected: a fixed list of
  tagged values, which needs an edit for every new annotation.
- **DEC-3:** the tagged value `unique_key = <name>: <attr>, <attr>[; nulls=equal]` becomes a
  `unique_keys` entry with `rp_unique_scope`. `nulls=equal` writes `consider_nulls_inequal: false`,
  and the hard check refuses it until `unique-key-nulls-equal` lands. The converter does not wait
  for that change.
- **DEC-4:** an application root may be `is_a: Activity` if the stage-1 spike shows that the
  boundary check, the commit's activity recording and the event stream treat it as an ordinary
  aggregate. If the spike fails, the converter refuses `rp_mixins=Activity` on a root, naming the
  reason, and the consumer remodels. Source: owner, 2026-11-20.
- **DEC-5:** the rule table stays open to new consumer rules until stage 2 starts, then freezes.
  Later rules go to a follow-up issue. Source: owner, 2026-11-20.
- **DEC-6:** the converter lives in `rdf_persistence_generation/` and the library does not import
  it (`library-never-imports-the-generator`). The command is a console script beside `rp-generate`.
  Rejected: a separate package.

## Rabbit-holes

- EA's `.qea` tables (`t_object`, `t_attribute`, `t_connector`, `t_objectproperties`, `t_xref` for
  stereotypes): read only what the rules need. Diagrams, layout and versioning are not read.
- Boundaries are diagram objects, not model containment. The containment test ("a root and other
  classes inside one boundary") must be pinned down in the PLAN on a real `.qea` before it is coded.
- Rule creep (DEC-5): until the freeze, a new rule is accepted only if it fits the appetite. If it
  does not, it goes to a follow-up, not into a silently larger EPIC.
- The model2owl / schema-automator chain of the analysis diagram is not used.

## No-gos

- No XMI input, no LinkML → UML, no diagram output.
- No change to the library (`rdf_persistence/`) except what the DEC-4 spike shows is required. Any
  such change is planned as its own task with its own test.
- No consumer-specific rule or term: all fixtures use a generic library model (`lib:Book`,
  `lib:Loan`…).
- No merging into hand-edited LinkML: the output is regenerated whole.

---

## What Changes

- New command `rp-uml2linkml` and its module in `rdf_persistence_generation/`.
- A small generic `.qea` fixture (built by a test helper, not checked in as a binary if avoidable)
  and golden LinkML output.
- How-to page "Generate the model from UML", with its question added to `questions.adoc`.

## Capabilities

### New Capabilities

- `rp-uml-import`: converting a UML class model into toolkit-conformant LinkML.

### Modified Capabilities

- `rp-generation`: lists the UML front end as a source of the LinkML.

## Impact

Generator package only. New console script in `pyproject.toml`. No new dependency (stdlib
`sqlite3`).
