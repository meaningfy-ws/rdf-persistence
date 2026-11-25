<!-- Parents: issue #208 (seed, inputs/seed.md); the archived change 2026-11-21-uml-to-linkml
     (PD-14, PD-27, D-5: the converter's merge is a stopgap until the generator learns cycles);
     the lead's planning brief of 2026-11-22. -->

# EPIC: Generated modules that import each other load, and the converter stops merging them

**Golden-thread parents:** issue #208; `openspec/changes/archive/2026-11-21-uml-to-linkml/`
design.md PD-14 (first branch: one module per package), PD-27 and D-5 (the merge, "until the
generator learns cycles"); `rp-generation` requirement "LinkML may be generated from a UML class
model"; `rp-uml-import` requirement "A UML class model converts to toolkit-conformant LinkML".

## Appetite

**MEDIUM.** One new generator capability (a target whose modules import each other generates
Python that loads) with its tests and docs, and one neighbour touched lightly: the UML converter
loses its merge. Two stages, one pull request each (DEC-6).

## Why

`rp-generate` accepts two domain modules that import each other and then writes Python that
cannot be imported: each split pydantic module imports the other's class at its top, so loading
either fails with a circular `ImportError` (#208). The import check (#242) now reports it, but the
schema has no way through. UML models have packages that refer to each other (the first
consumer's model had 15 such pairs), so `rp-uml2linkml` writes the packages of each cycle as one
module: the module layout then no longer follows the packages the modellers drew, and a change in
one association can move classes between modules. Both workarounds go once the generator handles
cycles.

## Solution outline

1. **Stage 1, the generator (#208).** When the modules a target generates import each other, the
   Python step writes them so they load in any order: a class of another module in the same import
   cycle that is only named in annotations is imported for the type checker only, and the
   package's `__init__.py` binds those names and rebuilds the models once every module of the
   cycle is loaded. A module in no cycle is written exactly as today, so no existing generated file
   changes. A cycle whose classes need each other while their modules load (a parent class, a
   default instance, a union) cannot be loaded by Python in any form, and `rp-generate` refuses it
   naming the modules and the classes.
2. **Stage 2, the converter.** `rp-uml2linkml` writes one module per package, always; packages
   that refer to each other become modules that import each other. The merge, its report line
   `merged-cycle` and the rule on the kinds of merged packages go, with their tests and the text
   of the docs and specs that describe them.

Outcome: the SPIKE-2 pair (`app_books` <-> `app_shelves`) and the converter's own cyclic library
generate, import and validate; the toolkit's generated files and the converter's golden output do
not change.

## Key decisions

- **DEC-1:** cycles are loaded by deferring annotation-only imports (`if TYPE_CHECKING:`) and
  completing the models in the package's `__init__.py` (bind each deferred name into its module,
  then `model_rebuild()`), as probe P-2 showed (inputs/codebase.md F-3). Reason: every class stays
  in the module of its schema module, so the import paths consumers use do not move, and
  `typing.get_type_hints` keeps working. Rejected: one Python module per strongly connected
  component (#208's second option): the classes' module changes, each schema module becomes a
  re-export shim, and the generator would have to build a merged schema, which is the converter's
  workaround moved one layer down.
- **DEC-2:** the change applies only to the modules of a target that are in an import cycle with
  each other (a strongly connected component of two or more of the target's generated modules, from
  the imports the Python step writes). Every other module, and the `__init__.py` of a target with
  no cycle, is byte-identical to today's. Reason: no regenerated diff in the toolkit or any
  consumer without cycles. Rejected: defer every import between generated modules (every
  generated file changes, for nothing).
- **DEC-3:** a cycle whose modules need each other's classes at import time is refused by the
  Python step (a `SchemaGenerationError`, so a `python:` problem line and exit 1), naming the
  modules and the names; there is no fallback merge in the generator. Reason: Python cannot load
  it, and a merge would silently move classes between modules. Rejected: merging such a component
  into one module.
- **DEC-4:** the converter writes one module per package, with no merge, no `merged-cycle` report
  kind (removed from `rp_generation.yaml`) and no rule on the kinds of merged packages. A cycle
  between a domain and an access package is then refused by `rp-generate`'s boundary check, which
  already refuses a domain module that imports an access one (F-12). **BREAKING** for a consumer
  that converted a model with a cycle: its merged module splits into one module per package, and
  the generated classes of the later packages move to their own Python modules.
- **DEC-5:** #206 (two slots on one `slot_uri`) is not in this EPIC (No-gos; `inputs/qa.md`
  OPEN-1).
- **DEC-6:** two stages, one PR each into `develop`: stage 1 (generator) closes #208; stage 2
  (converter) starts on `develop` once stage 1 is merged, because its tests generate the converter's
  cyclic output.

## Rabbit-holes

- **The parallel EPIC `converter-hardening` (#229 et al.).** #229 asks to move "the import-graph
  code" out of `convert.py` and to take `module_kind`/`domain` from the generated enums; stage 2
  edits the same functions (`_merge`, `_module_graph`, `_settle`, `Layout`, `_module_kinds`).
  Dependency: stage 2 merges first, and `converter-hardening` plans its #229 structure items on the
  converter without the merge; if it starts first, stage 2 rebases on it. Neither EPIC carries the
  other's item.
- Rewriting the stock pydantic templates wholesale: only the imports block and the rebuild footer
  of a module in a cycle change.
- Making acyclic modules lazy "for consistency" (DEC-2).
- Re-deriving shared-slot homes: `choose_homes` and `shared_edges` stay; only the merge map they
  read becomes the identity.

## No-gos

- #206 (refusing two slots that share one `slot_uri`): a different check with its own open
  decision (whether the identifier slot is exempt; the converter's golden output has
  `identifier` on `dcterms:identifier` beside the toolkit's `id`, inputs/codebase.md probe P-3). Its own TINY
  EPIC, or `converter-hardening` (OPEN-1).
- Cycles between modules of different targets (different `python_package`s): the import check
  keeps reporting them.
- Loading a cycle whose classes need each other at import time (DEC-3).
- Any change to the TypeScript, SHACL, JSON-LD context, frames, OpenAPI or diagram renderers: they
  already accept a cycle (F-6).
- A converter option to keep merging.

---

## What Changes

- `rp-generate`'s Python step loads a target whose generated modules import each other (#208).
- `rp-generate` refuses a cycle whose classes need each other at import time, naming them.
- **BREAKING** `rp-uml2linkml` writes the packages of an import cycle as separate modules that
  import each other; the `merged-cycle` report line and the `ReportKind.merged_cycle` value are
  gone; packages of different kinds in a cycle are no longer a converter problem (rp-generate's
  boundary check refuses a domain module importing an access one). Two same-named sibling
  packages with different kinds stay a converter problem (D-9).
- Docs: the UML conventions page (packages, module kind, shared slots, problems table), the UML
  how-to's report table, the generator's architecture page and user-manual page on generated
  Python, `CHANGELOG.md`.

## As delivered (P-0004)

| Item | State | PR |
|---|---|---|
| Stage 1: the generator loads module cycles, refuses load-time cycles (#208 closed) | delivered | #358 |
| Stage 2: the converter writes one module per package, no merge | delivered | #368 |
| RISK-6: the converter's start-up check re-run on a cyclic pair (owner, 2026-11-24) | delivered, task 2.4 | #368 |
| Stage 1's W1: the refusal test asserts the `python` step and untouched earlier output (D-5) | delivered | #368 |
| RISK-1: the consumer's model converted and generated on the stage 2 branch | checked by the lead, no change, no refusal (D-7) | #368 |
| #206: two slots on one `slot_uri` | not delivered: its own TINY EPIC (owner's answer OPEN-1) | — |

Delivery decisions D-1 to D-9 and what was left under the floor: design.md, *Delivery
decisions*. The cycle analysis result became a LinkML class in `rp_generation.yaml` (D-1),
not a hand-written record.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-generation`: a requirement added: modules of one target that import each other generate
  Python that loads; a cycle needing classes at import time is refused.
- `rp-uml-import`: the conversion requirement no longer merges the packages of a cycle.

## Impact

- Code: `rdf_persistence_generation/extensions/pydantic_split.py`, the new pure module
  `rdf_persistence_generation/module_cycles.py`, the override
  `rdf_persistence_generation/templates/pydantic/module.py.jinja`, `uml/convert.py`,
  `uml/slots.py`, `uml/modules.py`, `model/rp_generation.yaml` and its generated files.
- Tests: `tests/generator/{unit,integration,feature}` (design.md *Tests*).
- Consumers: a converted model with a cycle gets more modules on its next conversion (DEC-4).
