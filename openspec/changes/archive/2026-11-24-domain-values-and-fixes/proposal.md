<!-- Parents: issues #301, #303, #302, #300 (inputs/seed.md); openspec/specs/rp-generation,
     rp-package-boundaries, rp-testkit, rp-service-api.
     Serves (D-12): MWB2 v2-05-target-and-fragments stage 1 (task 1.1, its D-6) waits on #301;
     MWB2 v2-02's open round-trip and workflow-route tests wait on #303, #302 and #300. -->

# EPIC: Domain value modules, and three fixes a consumer waits on

## Appetite

**MEDIUM**, in four stages, one PR each, in the order the consumer needs them: #301 (one new
capability, a module kind), then #303, #302 and #300 (one defect each, existing structure reused).

Shaped by the lead with the developer's instruction to work independently (2026-11-23): no question
rounds were sent; each open question is decided below as a `DEC-` with the option rejected, for
the developer to review in the PRs.

## Why

- **#301.** Pure domain logic (a check, a comparison) returns results that are domain concepts but
  are never stored: a status enum, a finding, a report. Today no generated class can be one. A
  domain module refuses a class that is neither a root nor owned, and a technical module, which
  allows it, may only be generated into `services`, `adapters` or `entrypoints`, which the domain
  layer must not import. A LinkML-single-source consumer cannot hand-write them either.
- **#303.** A slot whose range is an *abstract* aggregate root is generated as an embedded object,
  while a concrete root gives an IRI. A reference to an aggregate is always an IRI, so the
  generated class refuses valid instances and the testkit's round trip fails.
- **#302.** The testkit's `aggregate` strategy draws values the class's own `slot_usage` refuses
  (`equals_string`, `multivalued`), so the round trip fails for every reference collection the
  converter writes.
- **#300.** The how-to tells a consumer's route to call `expected_version`, which the top level of
  `rdf_persistence` does not export; a consumer that imports only the top level writes its own,
  weaker `If-Match` parser.

## Solution outline

- **A value module.** A module annotated `module_kind: value` holds domain values: classes and enums
  for the domain layer that are never stored. Its target lives in the domain layer
  (`<pkg>.domain.generated[.<group>]`, corrected in delivery, design.md D-8). Its classes get none of the stored-class rules (ownership, roots,
  IRIs, routes), as a technical module's do, and the layer rules hold: domain and technical modules
  may import it, it imports only domain, value and toolkit core modules, and it never declares a
  root. A technical module importing it gets its classes through the existing cross-target import,
  so both sides hold the same Python class.
- **A reference to a root is an IRI, abstract or not.** Python `str`, TypeScript `string`, shape
  `sh:nodeKind sh:IRI`, decided in one place every generator reads.
- **The strategy draws what the class accepts.** Each slot is drawn from the class's induced slot,
  `slot_usage` applied: `equals_string` gives that value, `multivalued` a list.
- **The version helpers are public.** `expected_version` and `matched_version` are top-level names,
  and the guides import them from there.

## Key decisions

- **DEC-1:** a fourth value of `ModuleKind`, `value`, in the metamodel (`rp_core.yaml`); the rules
  key on it per module, as they do for `technical`. Rejected: a per-class annotation (the boundary
  rules work per module, and a class-level flag invites a stored class slipping out of the rules);
  letting a technical module into the domain folder (breaks `rp-package-boundaries`: no domain
  module imports a technical model).
- **DEC-2:** a value class is exempt from every stored-class rule a technical class is exempt from
  (ownership, owned-class and root rules of the boundary and hard checks), and a value class that
  is an aggregate root or a tenant root is refused (`module_kind` rule), as a technical one is.
- **DEC-3:** import direction. A value module may import domain, value and toolkit modules; a
  domain or technical module may import a value module; a value module importing a technical or an
  access module is refused, with the hint to move the class into a value or domain module.
- **DEC-4:** a value module is a domain-layer module for the target rules: its target's folder is
  `domain` before `generated`, and it may share a target with domain modules. No new `TargetKind`.
  Rejected: a third target kind (no folder rule would differ).
- **DEC-5:** a stored class never holds a value class, inline or by reference: a value is never
  stored (the holding rule, extended from technical classes). A stored class may use a value
  module's enum, since an enum is a literal. A technical or value class may hold a value class.
- **DEC-6:** a slot whose range has `AggregateRoot` among its ancestors and is not owned is a
  reference in every generated artefact, whether the range is abstract or concrete. The fix sits
  where the inlining is decided once for all readers, found test-first (as `slot-resolution`
  DEC-3). Rejected: patching the Python template alone (TypeScript and the shapes would disagree).
- **DEC-7:** the strategy draws from the induced slot of the class being drawn, `equals_string`
  and `equals_string_in` honoured; the other narrowings (`range`, `required`, `pattern`, bounds)
  follow from the induced slot. Root cause found test-first.
- **DEC-8:** `expected_version` and `matched_version` are exported lazily from `rdf_persistence`
  (the guides tell a consumer to use both); `howto/workflow.adoc` and `architecture/api.adoc` show
  the top-level import. Rejected: moving the functions (their module stays where the routes use it).
- **DEC-9:** one change, four stages, four PRs into `develop`, in the order #301, #303, #302, #300.
  This EPIC lands with stage 1's PR; each later PR ticks its stage in `tasks.md`.

## Rabbit-holes

- The cross-target import must hand a technical target the value classes, not regenerate them: a
  value module needs `python_package`, as any module another target imports.
- The UML converter reads a package's `module_kind` tagged value; accepting `value` there is the
  same enum, so it comes for free. Nothing else in the converter changes.
- #303: the stock generators decide inlining from the range's identifier; an abstract class whose
  identifier comes through a mixin may be read as having none. Find which reader decides before
  changing anything.
- #302: `class_induced_slots` already applies `slot_usage`; the defect may be in how a value is
  drawn (`equals_string` is never read) or in a view that is not the class's. Reproduce first.

## No-gos

- No storage, routes, IRIs or events for a value class; no value module in the services, adapters
  or entrypoints layers.
- No new target kind, no new boundary rule enum value: the existing `module_kind` and
  `target_kind` rules carry the new problems.
- No change to how an owned part is embedded.
- No new testkit strategy or option; the existing `aggregate` gets correct.
- No other public names exported in #300.

---

## What Changes

- Metamodel: `ModuleKind` gains `value`.
- Generator checks: the technical exemption covers value classes; folder, import, holding and root
  rules learn the value kind.
- Generator: a slot over an abstract root is generated as an IRI.
- Testkit: `aggregate` honours `slot_usage`.
- Public API: `expected_version`, `matched_version` at the top level.
- Toy library: a value module in the domain layer, used by a domain module and a technical one; an
  abstract root and a slot over it; a class with `slot_usage` `equals_string` and `multivalued`.
- Docs: `architecture/generation.adoc` (value modules), `howto/workflow.adoc`, `architecture/api.adoc`.

## Capabilities

### Modified Capabilities

- `rp-generation`: value modules; a reference to an abstract root is an IRI.
- `rp-package-boundaries`: the domain layer may import a value module.
- `rp-testkit`: the aggregate strategy honours `slot_usage`.
- `rp-service-api`: the version helpers are public.

## Impact

Metamodel (`rp_core.yaml`, regenerated), generator (`checks/boundary.py`, `checks/hard.py`, the
place #303 finds), testkit (`rdf_persistence_generation/testkit/strategies.py`), the top package,
the toy library, three docs pages. For a consumer after the bump: `module_kind: value` is accepted;
a slot over an abstract root becomes `str` in its generated code (a breaking change for code that
built the embedded object, which no valid instance could reach); its round trips pass for
`slot_usage` classes.

## As built

Reconciled after the last merge (P-0004 asks for it before; recorded late, nothing differs from
the merged code). Delivered in four PRs, merged into `develop` on 2026-11-24 on the local gate
(P-0021, GitHub CI suspended):

| Stage | Issue | PR | State |
|---|---|---|---|
| 1. Value modules | #301 | #313 | built as shaped, with D-8 (package `domain.generated[.<group>]`), D-9 (direct imports only) and D-10 (nested mypy folders) |
| 2. Abstract root as IRI | #303 | #314 | built; the fix sits in `load_schema` and `apply_defaults` (D-11), not only `apply_defaults` as D-4 planned; `load_schema` rated CRITICAL by GitNexus, flagged (D-12) |
| 3. `slot_usage` in the strategy | #302 | #315 | built; the multivalued case was a JSON-LD context defect, fixed with type-scoped terms (D-14), which also corrects the API's framed JSON |
| 4. Version helpers public | #300 | #316 | built as shaped |

- What Changes, Capabilities and Impact hold as written, with two additions: the context extension
  (`extensions/jsonld_context.py`) and `load_schema` changed, and the generator's mypy step
  (`checks/importable.py`).
- Promised but not built: nothing. Out of scope as planned: TypeScript across targets for value
  modules (D-3), `python_package` from the UML converter (D-6).
- The spec deltas are true of the code.
