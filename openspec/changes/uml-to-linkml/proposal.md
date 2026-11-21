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
- How-to page "Generate the model from UML", with its question added to `questions.adoc`, and a
  reference page "UML conventions" (D-20).

## Capabilities

### New Capabilities

- `rp-uml-import`: converting a UML class model into toolkit-conformant LinkML.

### Modified Capabilities

- `rp-generation`: lists the UML front end as a source of the LinkML.

## Impact

Generator package only, plus `Review` in the toy model as the guard of DEC-4 (PD-34). New console
script in `pyproject.toml`. No new dependency (stdlib `sqlite3`).

---

## Delivery reconciliation

What was delivered against this shape, stage by stage (rule P-0004). The decisions are in
[design.md](design.md#delivery-decisions); this table only names them.

| Shaped | Delivered | Why | Decision | PR |
|---|---|---|---|---|
| One module per UML package | One per package, except the packages of an import cycle, written as one module with a `merged-cycle` report line | Split Pydantic modules do not import across a module cycle (SPIKE-2 failed; #208) | D-5 | #212 |
| The output passes `rp-generate`'s lint and boundary check unchanged | True when every class, slot and enumeration has a note; a missing note gets no placeholder and a `no-note` report line | Lint refuses an element without a description; a placeholder would hide the gap | PD-28, D-21 | #212 |
| Multiplicity `0\|1 .. 1\|*`; a missing one fails (PD-32) | Any `m..n`, with `minimum_cardinality`/`maximum_cardinality`; a missing one is `0..*` with a report line; `1..1` for exactly one; an attribute's bounds as stored, since EA writes a blank as `1..1` | Alignment with the model2owl conventions (developer, round 3) | D-11 | #212 |
| An enumeration becomes an enum | An enumeration with no literals (an external code list) gives `range: uri` and an `external-list` line | model2owl's controlled-list convention | D-10 | #212 |
| The XSD datatype map | `rdf:langString` and `rdf:PlainLiteral` fail the run until the toolkit has a language-string range; never narrowed to a plain string | Language strings must not be lost (developer); the toolkit change is #209 | D-12 | #212 |
| Unknown stereotypes fail | The «Abstract» stereotype is accepted as `abstract: true` | model2owl draws abstract classes with it | D-13 | #212 |
| Connector direction not read | Only `Source -> Destination` (target role) or `Bi-Directional` (both roles) | model2owl's direction rule | D-14, D-18 | #212 |
| Explicit `class_uri` on every class | No `class_uri` when it equals the implicit one | `modelling-conventions` rule 2 | D-14 | #212 |
| `--exclude-package` | One that matches no package is a usage error; the reader also names the far ends of links it leaves out | A typo must not convert everything; the report names left-out targets | D-17 | #212 |
| An application root may be an `Activity` (DEC-4, if the spike passes) | Allowed: SPIKE-1 passed with no library change; `Review` stays in the toy as its guard | — | D-7 | #212 |
| One how-to page | Also a UML conventions reference page with UML snippets | The developer asked for the toolkit's conventions to be written down | D-20 | stage 2 |
| The rule table open until stage 2 | Frozen at R-1..R-30: one rule (R-30) added after a read-only run on the consumer's real model | An enumeration of workflow states is not generated, like a loaded graph | D-20, D-23 | stage 2 |
| Toolkit-aware rules R-15, R-18, R-20..R-29 | Delivered as planned, plus: a «tenant root» takes the default mixins; a shared slot's home is the module the others reach transitively, and a cycle that sharing creates is merged; a `unique_key` may name a role or a reused toolkit slot; a toolkit class drawn inside the package is used, not generated | The toolkit's own tenant class has them; the real model's shared slots span packages; found while building | D-26, D-27 | stage 2 |
| R-30 for not-generated stereotypes | Enumerations only; a not-generated class keeps its stage-1 behaviour | An attribute typed by a class must still fail (I-1) | D-26 | stage 2 |
| The reader reads connectors between classes | It skips any connector with a note, text, boundary or package at an end, whatever its type | An association drawn to a note crashed the converter | D-25 | stage 2 |
| The converter's records are generated models (PD-2) | Also its working data (`Element`, `PackagePath`, `End` as generated records; slot shapes as `SlotDefinition`); the per-call processing state stays hand-written | Stage-1 review W-1 | D-24 | stage 2 |
| The generated output passes `rp-generate` (G-2) | The stage-2 golden passes lint, boundary, hard and rules, is generated in write mode and imports; the real model converts once its own clashes are fixed, and passes `rp-generate` once its missing notes are added too ([acceptance](evidence/acceptance.md)) | RISK-2: a quarter of the real model has no notes | D-29 C-4 | stage 2 |

Not delivered: nothing the shape promised is left out. Upstream: #208 (cyclic split modules) and
#209 (a language-string range) stay open in the toolkit; the converter refuses or merges until they
land.
