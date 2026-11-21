<!-- Secondary input, never groomed: GitHub issue #196 (meaningfy-ws/rdf-persistence), fetched 2026-11-20. The EPIC (../proposal.md) supersedes it. -->

# #196 Generate LinkML from a UML class model (Enterprise Architect .qea / XMI)

## Summary

Generate a toolkit-conformant LinkML schema from a UML class model drawn in Enterprise Architect
(`.qea`, the SQLite project file) or exchanged as XMI, so that a team can keep UML as the modelling
source and regenerate LinkML (and from it everything `rp-generate` produces) instead of porting the
model by hand.

## Context

- Consumer: Mapping Workbench 2 (`meaningfy-ws/mapping-workbench-v2`), change `domain-model-v2`
  (decision S6-12) and the planned EPIC `v2-02-model-from-ea`.
- The domain model (≈40 classes in 8 packages) is drawn in tandem with a domain expert in Enterprise
  Architect; the team wants EA to stay the source and LinkML to be regenerated from it.
- Locked toolkit commit: `6bf3471` (upgrade to v0.7.0 planned); read against `origin/develop` `c671fefb`.
- No importer exists today (only an analysis diagram in
  `openspec/changes/archive/2026-11-05-soa-python-rdf-orm/inputs/analysis/integration-diagrams/c1-uml-to-linkml.puml`:
  EA XMI → model2owl → schema-automator → LinkML).

## What is missing

A command that reads a UML class model and writes one LinkML module per UML package, already
marked with the toolkit's metamodel (aggregate roots, owned slots, module kind), so that `rp-generate`
runs on it unchanged. Converting by hand is slow and drifts from the drawing on every modelling round.

## Proposed capability

`rp-uml2linkml` (or a `rp-generate` front end), reading `.qea` directly (stdlib `sqlite3`, no EA
licence needed) and XMI 2.x as a second input.

```
rp-uml2linkml model.qea --package MODEL --prefixes prefixes.yaml --out models/ [--root-name app]
```

Mapping rules (all configurable defaults):

| UML | LinkML |
|---|---|
| package | one module file `<root>_<package>.yaml`, `module_kind: domain`; a root schema importing them |
| class `pfx:Name` | class `Name`, `class_uri: pfx:Name`; a class named with a foreign prefix (`skos:Concept`) reuses that IRI |
| abstract class | `abstract: true` |
| generalisation | `is_a` (first parent), `mixins` (others) |
| attribute `pfx:name : xsd:T [l..u]` | slot `name`, `slot_uri: pfx:name`, `range` from the XSD map, `required` when l ≥ 1, `multivalued` when u is `*` |
| association with destination role `pfx:role` and multiplicity | slot on the source class, `slot_uri: pfx:role`, `range` = destination class, cardinality as above |
| enumeration | enum; literals → permissible values with `meaning` when prefixed |
| dependency class → enumeration, named by the role (SEMIC style) | enum-ranged slot |
| notes on class, attribute, connector | `description` |
| stereotype «root» | `mixins: [AggregateRoot]` + `rp_path` annotation (derived from the class name, overridable) |
| boundary containing a root and other classes, or an association marked composite | the slots from the root to those classes `owned: true` |
| a stereotype listed as "not generated" (e.g. «loaded graph») | no class; documented only |
| the same slot name on several classes with the same `slot_uri` | one shared slot (reuse), `slot_usage` for differing ranges or cardinalities |

Example of the intended use:

```python
# model.qea, package MODEL/library: «root» lib:Book (dct:title : xsd:string [1..1]) --lib:hasChapter 1..*--> lib:Chapter,
# both inside one boundary; lib:Book --lib:shelvedOn 0..1--> «root» lib:Shelf
```

```yaml
# models/app_library.yaml (generated)
classes:
  Book:
    class_uri: lib:Book
    mixins: [AggregateRoot]
    annotations: {rp_path: books}
    slots: [title, has_chapter, shelved_on]
slots:
  title: {slot_uri: dct:title, range: string, required: true}
  has_chapter: {slot_uri: lib:hasChapter, range: Chapter, multivalued: true, required: true, annotations: {owned: true}}
  shelved_on: {slot_uri: lib:shelvedOn, range: Shelf}
```

## Why it belongs in rdf-persistence

Any model-driven RDF application whose domain experts draw UML needs it, and the output must carry
the toolkit's own metamodel (roots, owned parts, module kinds), which only the toolkit can keep in step
with its generator and boundary checks. The toolkit already owns the generation chain from LinkML.

## Acceptance

- **Given** a `.qea` with a package of classes, attributes, associations, generalisations, an
  enumeration linked by a dependency and a «root» class in a boundary with a part, **when**
  `rp-uml2linkml` runs, **then** it writes one module per package that passes `rp-generate`'s lint and
  boundary check, with the URIs, cardinalities, descriptions, root mixin and `owned` slots above.
- **Given** the same model exported as XMI 2.x, **when** converted, **then** the output equals the
  `.qea` output.
- **Given** an element the rules cannot map (an association class, an n-ary association), **when**
  converted, **then** the command fails naming the element and the rule missing, writing nothing.
- **Given** a converted schema and an unchanged model, **when** converted again, **then** the output is
  byte-identical (stable order), so a freshness check can run in CI.

## Impact on the consumer

The consumer's LinkML EPIC waits for this capability (it does not write its own converter). Until
then it upgrades the toolkit. A partial first version (`.qea` only, no XMI) unblocks it.


## Comments

--
Further rules the first consumer needs (Mapping Workbench 2, change `v2-02-model-from-ea`, design §mapping rules 14–19), found by checking its UML model against the rule table above. Without them the converted schema would redefine toolkit classes and slots instead of reusing them. Written generically:

| UML | LinkML |
|---|---|
| generalisation to a toolkit class (`rp:StoredFile`, `rp:ReferenceCollection`, `rp:UnderWorkflow`, `rp:Described`, `rp:Tracked`, `prov:Activity`) | import of the toolkit module and a mixin (or `is_a` for a class such as `Activity`); no new class |
| attribute or role whose IRI is the `slot_uri` of a slot of an imported toolkit class (`skos:prefLabel`, `dct:description`, `prov:hadMember`, `prov:startedAtTime`, …) | that toolkit slot, not a new one |
| association to a class that is not generated (outside the converted packages, or a stereotype listed as not generated) | slot with `range: uri` |
| tagged values on a class (`rp_path`, `workflow`, `graph`, `rp_unlabelled`, `database`) | class `annotations` with the same names |
| stereotype «tenant root» | the class annotated `graph: meta`, without `AggregateRoot` |
| class or slot without a title | `title` = the name split into words |

Example: `«root» lib:Loan` generalising `prov:Activity`, with `prov:startedAtTime : xsd:dateTime [1..1]` and a tagged value `rp_path=loans` → `Loan: {is_a: Activity, mixins: [AggregateRoot], annotations: {rp_path: loans}, slot_usage: {started_at_time: {required: true}}}`, importing `rp_provenance`, with no new `started_at_time` slot.

Open question for the toolkit: may an application aggregate root be `is_a: Activity` (a run recorded as a PROV activity that is also a stored aggregate)? The consumer's validation runs are modelled that way.

--
--
Two follow-ups for the UML converter, raised while planning MWB2 `v2-03-project-and-resources` and `v2-05-target-and-fragments` (toolkit `c671fefb`):

1. **Carry `rp_writes`.** Rule 17 maps the class tagged values `rp_path`, `workflow`, `graph`, `rp_unlabelled` and `database` to class annotations, but not `rp_writes`. Proposal: every class tagged value named like a toolkit class annotation becomes that annotation, checked against its enum (`WritesKind`). Acceptance: a UML class tagged `rp_writes=service` converts to `annotations: {rp_writes: service}`, and the API serves no `POST` for it.
2. **Map unique keys.** A class tagged value `unique_key = <name>: <attr>, <attr>[; nulls=equal]` becomes a `unique_keys` entry (with `rp_unique_scope`, and `consider_nulls_inequal: false` for `nulls=equal`, which depends on the nulls-not-distinct issue). Acceptance: a `Book` tagged `unique_key = title_subtitle: title, subtitle` converts to the matching `unique_keys` block.

--
--
Three more rules the first consumer needs, found while readying its UML model for conversion (Mapping Workbench 2, change `v2-02-model-from-ea`, task 1.3, toolkit `c671fefb`). Written generically:

1. **An attribute named `dct:identifier` is not the identifier slot.** Rule 15 (reuse the toolkit slot whose `slot_uri` matches) must skip `id`: it is `identifier: true`, the object's IRI, and never a triple. A UML attribute `dct:identifier : xsd:string` is a business identifier (a short code a person types) and becomes a new slot `identifier`, `slot_uri: dcterms:identifier`, `range: string`. Acceptance: `lib:Book` with `dct:identifier : xsd:string [1..1]` converts to a required string slot `identifier`, and the class keeps the toolkit's `id` as its IRI.
2. **Abstract parents of roots.** An abstract class whose concrete subclasses are all «root», and which is the range of a pointer, gets `mixins: [AggregateRoot]` without an `rp_path`; each concrete subclass gets its `rp_path`. The UML does not mark the abstract class «root» (the stereotype means one aggregate box). Acceptance: abstract `lib:Item` with «root» subclasses `lib:Book` and `lib:Map`, pointed to by `lib:Loan.lib:item`, converts to `Item: {abstract: true, mixins: [AggregateRoot]}`, and the slot `item` ranges over `Item`.
3. **One slot used in several packages.** When the same role or attribute name with the same IRI appears on classes of several packages (rule 13), the slot is defined once, in the module the others import, and narrowed through `slot_usage` elsewhere; when no such module exists, the converter fails naming the slot and the packages. Acceptance: `lib:hasParent` on `catalogue:Section` and on `shelves:Shelf`, where `shelves` imports `catalogue`, is defined in `lib_catalogue` only.

--
--
Revision of two rules in the first consumer's earlier comments (Mapping Workbench 2, change `v2-02-model-from-ea`, after the domain expert's review of its UML model). Written generically:

1. **The toolkit is not drawn (replaces "generalisation to a toolkit class").** The UML holds domain classes only; drawing the toolkit's classes and dozens of generalisations to them buries the domain. Proposal:
   - every class the converter makes a root (`«root»`) or a part with a label gets the toolkit's `Described` and `Tracked` mixins by default (configurable list, e.g. `--default-mixins Described,Tracked`); a part tagged `rp_unlabelled=true` gets neither label slot;
   - a class tagged value `rp_mixins=<Class>[,<Class>…]` names further toolkit classes; a mixin class becomes a mixin, a non-mixin class (`Activity`) becomes `is_a`; their modules are imported;
   - a class tagged `workflow=<name>` gets `UnderWorkflow` (the annotation already says it is under a workflow).

   Acceptance: `«root» lib:Book` tagged `rp_mixins=StoredFile` converts to `Book: {mixins: [AggregateRoot, StoredFile, Described, Tracked]}`, importing `rp_files` and `rp_annotations`; `«root» lib:Loan` tagged `rp_mixins=Activity` converts to `Loan: {is_a: Activity, mixins: [AggregateRoot, Described, Tracked]}`; a UML generalisation to a toolkit class is still accepted, so models that draw it keep working.
2. **Links to classes the conversion leaves out (refines "association to a class that is not generated").** An association to a class whose stereotype is listed as not generated (a loaded graph) becomes a slot with `range: uri`, as before. An association to a class in a package excluded from the conversion (`--exclude-package`) is not converted at all and is listed in the converter's report, so an application can model a part of its domain later without committing to links into it now. Acceptance: with `--exclude-package circulation`, `lib:Book → circulation:Loan lib:currentLoan` produces no slot and one report line naming the association.

--
