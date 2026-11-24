# Design: domain-values-and-fixes

EPIC: `proposal.md` (#301, #303, #302, #300). Decisions DEC-1 to DEC-9 are the EPIC's; the
delivery decisions below are D-n, added as the stages run.

## 1. Value modules (#301)

### Algorithm

`ModuleKind.VALUE` (`value`) joins the enum in `rdf_persistence/model/rp_core.yaml`; `make generate`
regenerates `rp_core.py` and its dependants. In `rdf_persistence_generation/checks/boundary.py`:

| Function | Today | After |
|---|---|---|
| `technical_classes` | classes of `technical` modules | keeps its name (used by `hard.py`) and returns the classes of `technical` **and** `value` modules; its docstring says so (D-1) |
| `_ownership_problems`, `hard._stored_classes` | exempt technical | exempt technical and value (follows from the line above) |
| `_never_stored_root_problems` | a technical root refused | a technical or value root refused; the message names the kind |
| `_module_problems` | a `domain` module importing `technical`/`access` refused | unchanged for domain (value allowed, DEC-3); plus: a `value` module importing `technical`/`access` refused, hint "move the class into a value or domain module" |
| `_holding_problems` | a non-technical module holding a technical class refused; `homes` built from the target's own modules only | `homes` (the never-stored classes and their kind) is built from **every module of the view** (`view.schema_map`), so a value or technical class of another folder is found (D-2, gate counterexample 1). Then: a stored module (domain, access, none) holding a technical or value class, in a slot or through `is_a`/`mixins` (`class_ancestors`), is refused; a value module holding a technical class is refused; technical holds anything, value holds value (DEC-5). `_reference_problems` skips a slot whose range is in `homes`, so the holding rule alone reports it |
| `derived_kind`, `mixed_kind_problems` | technical iff all own modules technical | unchanged: a value module is not technical, so a value target, or a domain+value one, is a domain target (DEC-4); value + technical in one target stays refused as mixed |
| `_folder_message` hint | "if its modules are technical, annotate them module_kind: technical" | adds "; a value module stays in domain" |

The hard check already reads the allowed `module_kind` values from the enum (`hard.py` ~l.91), and
the UML converter does too (`uml/tags.py`, `uml/convert.py` `_module_kinds`), so both accept `value`
with no code change; nothing else in the code switches on `ModuleKind` (checked by the gate).

A value class's slot over a class: the reference rule (`_reference_problems`) runs only over stored
classes, so a value class may hold another value class inline without `owned: true`; the stock
generator inlines a class with no identifier, which a value class has none of. If a value class
holds a domain root, it is an IRI (as anywhere).

### Example (the toy, `tests/fixtures/library/`)

- `values/loan_checks.yaml`, `module_kind: value`, `python_package: library.domain.generated.values`:
  enum `LoanStatus`, classes `LoanFinding {code, message}`, `LoanCheck {status, findings}`.
- New `[[tool.rp-generate]]` entry: `schema = "values/loan_checks.yaml"`,
  `package = "library.domain.generated.values"`, with no `typescript` folder (D-3): TypeScript
  across targets is out of scope here (`typescript.py` writes only a target's own schemas); a
  consumer that needs the value types in TS sets `typescript` on the value target itself.
- A new technical module of the toy holds `LoanChecksResponse {checks: LoanCheck*}` and imports
  `loan_checks`; its generated Python imports `LoanCheck` from
  `library.domain.generated.values.loan_checks`.
- A domain module may import `loan_checks` and use `LoanStatus` on a stored slot (enum, DEC-5).

### Error matrix

Detection is the check named; the response is a `CheckProblem` that stops `rp-generate` (exit 1)
with the message shown; the fallback is the hint in the message. All rows are TC-1 rows.

| # | Input | Detection | Response / message (fragment) | Fallback the user takes |
|---|---|---|---|---|
| E1 | value module, target `library.domain.generated.values` | boundary, hard | none; Python generated | n/a |
| E2 | value module, target `library.services.generated` | `kind_folder_problems` | `target_kind`: "not in a folder a domain target allows … a value module stays in domain" | move the target to `domain` |
| E3 | domain module imports value module | `_module_problems` | none | n/a |
| E4 | technical module imports value module (value declares `python_package`) | boundary; generation | none; classes imported, not redefined | n/a |
| E5 | value module imports technical module | `_module_problems` | `module_kind`: "is a value module and imports X, a technical module: move the class into a value or domain module" | move the class |
| E6 | value module imports access module | `_module_problems` | `module_kind`, as E5 | as E5 |
| E7 | value class mixes `AggregateRoot`, or is a tenant root | `_never_stored_root_problems` | `module_kind`: "is an aggregate root in a value module: a value class is never stored" | drop the mixin |
| E8 | stored class slot over a value class, same folder, `owned` or not | `_holding_problems` | `module_kind`: "… holds LoanCheck, a class of the value module …: a stored class never holds a value" (not also `reference`) | use the value module's enum, or a domain class |
| E9 | as E8, value module in another folder (its own target) | `_holding_problems` over the view | as E8 | as E8 |
| E10 | stored class slot over a value enum | none | none | n/a |
| E11 | value class neither root nor owned | `_ownership_problems` | none | n/a |
| E12 | `module_kind: valeu` | hard annotation check (enum) | the annotation's value refused, and the classes stay stored (ownership problems) | fix the spelling |
| E13 | stored class `is_a` a value class, or mixes one in; a root subclass of a value class | `_ownership_problems` (non-root); `_holding_problems` (any stored class, via `class_ancestors`) | ownership problem for a non-root subclass; `module_kind` "holds X, a class of the value module …" for every stored subclass or mixer, root or not | drop the `is_a`/mixin, or move the class into a value module |
| E15 | stored slot over a technical class | `_holding_problems` | `module_kind` once, not also `reference` | move the class or the slot |
| E16 | `rp-generate` folder hint | `_folder_message` | "a value module stays in domain" only when a module of the target is `value` | n/a |
| E14 | value and technical modules in one target | `mixed_kind_problems` | `target_kind` mixed (unchanged) | split the targets |

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| A class-level flag (`rp_value: true`) | the module kind | the rules work per module; a flag lets a stored class slip out one class at a time |
| Patch the Python template alone for #303 | fix where all readers decide, or set it in `apply_defaults` | TS and the shapes would still embed, and disagree with Python |
| A value module imported across targets without `python_package` | declare it | it is regenerated into the importing target: two classes, `isinstance` fails |
| An `equals_string` branch after the `pattern` or enum branch in `_scalar` | put it first | a pattern or enum draw would win and still give a refused value |
| Build `homes` from the target's own modules | from the whole view | a value module in its own folder escapes the holding rule (E9) |

## 2. A reference to an abstract root (#303)

Root cause first (systematic debugging): find which reader decides the embedding. The gate found
that `_holds_objects` (`schema_structure` ~l.537) serves only the unique keys; TypeScript reads
`view.is_inlined` (`extensions/typescript.py` ~l.87); Python and the shapes come from the stock
generators. The fix goes where every generator reads it (DEC-6); if there is no single reader, it
sets `inlined: false` on each slot over a non-owned range with `AggregateRoot` among its ancestors
in `apply_defaults` (`schema_structure.py` ~l.458), which every generator consumes (D-4). Toy: a new abstract `Item` (`mixins: [AggregateRoot]`)
with two new concrete roots `Magazine` and `Pamphlet` (`is_a: Item`, own `rp_path`), leaving `Book`
untouched; a root `Loan` with `lends: {range: Item, required: true}`. Expect Python `lends: str`, TS `lends: string`, shape
`sh:nodeKind sh:IRI` on `lends`, and the round trip of `Loan` passing.

## 3. The strategy honours `slot_usage` (#302)

Reproduce with the toy's `BookCollection` (`slot_usage: member_class: equals_string: Book`) and a
`Shelf` with `holds` made multivalued by `slot_usage`. In `strategies.py`, `_scalar` returns
`st.just(slot.equals_string)` when set and `st.sampled_from(slot.equals_string_in)` when set,
before any other branch; the multivalued case follows from the induced slot once the cause is found.
If the RED for `Shelf.holds` does not reproduce on the toy, TC-6's multivalued row stays as a
regression test and the stage records in the PR and D-5 that it found no defect there (D-5).

## 4. The version helpers are public (#300)

Add `expected_version`, `matched_version` to `_LAZY_MODULES` (`f"{_API_ENTRYPOINTS}.negotiation"`),
the `TYPE_CHECKING` import block and `__all__`; `make refresh-surface` after (a deliberate new
public name). Docs lines named in the EPIC switch to `from rdf_persistence import expected_version`.

## Test cases

| Id | Issue | Test | Tier |
|---|---|---|---|
| TC-1 | #301 | `tests/generator/unit/test_value_modules.py`: rows E1 to E14 of §1 as parametrised tables over scratch projects (pattern of `test_technical_exemption_adversarial.py`) | generator unit |
| TC-2 | #301 | the toy generates `library.domain.generated.values.loan_checks`; the toy's technical module imports, not redefines, `LoanCheck` (`LoanChecksResponse(checks=[LoanCheck(...)])` holds the same class object). Python only (D-3) | generator unit |
| TC-3 | #301 | `make check-generated` / freshness: the toy and the toolkit regenerate clean | gate |
| TC-4 | #303 | generated Python and TS field types of a slot over an abstract root; the shape's `sh:nodeKind sh:IRI` | generator unit |
| TC-5 | #303 | toy `Loan` validates `lends` as an IRI and round-trips with `aggregate` + `round_trip` | generator unit |
| TC-6 | #302 | `aggregate` draws `member_class == "Book"` for `BookCollection` and a list for `Shelf.holds`; both round-trip | generator unit |
| TC-7 | #300 | `import rdf_persistence as r`, one parametrised table: `'"v1"'` → `"v1"`; `None` and `""` → `PreconditionRequired` (428); `'"a", "b"'` and `'*'` → `PreconditionRequired` (428, "must be one entity tag"); `'W/"v1"'` → `Conflict` (409); and `r.matched_version is negotiation.matched_version` | unit |
| TC-8 | all | the public-surface baseline and the scenario map carry the new names and tests | unit |

Spec deltas: `specs/rp-generation`, `specs/rp-package-boundaries`, `specs/rp-testkit`,
`specs/rp-service-api` of this change.

## Risks

- **RISK-1** (likelihood medium, impact medium): the enum value changes generated toolkit code and
  the shapes of the metamodel; a consumer's lock or snapshots may move. Mitigation:
  `make check-generated`, `make refresh-snapshot` only where the diff is the enum.
- **RISK-2** (high, low): #303 changes a consumer's generated type from a model to `str`; code that
  built the embedded object breaks at type check. Accepted: no valid instance could use it; the PR
  and the release notes say so (**BREAKING** in the generated code).
- **RISK-3** (medium, medium): the #303 fix in a shared reader changes other slots' inlining.
  Mitigation: every regenerated toolkit and toy artefact diff is read; only slots over an abstract
  root may change; GitNexus impact on the changed function before the stage's last commit.
- **RISK-4** (low, medium): a value module beside domain modules in one target puts value classes
  into the combined shapes/context. Accepted: harmless (no instance is ever stored); if it is not,
  the value module gets its own target, as the toy does.

## Attack (counterexamples taken into the PLAN)

- A stored class `is_a` a value class → stays stored (matrix row).
- A domain module reaches a technical one *through* a value module → the value module's own import
  of a technical or access module is refused (DEC-3); a path through an unannotated module is not
  walked (D-9).
- A value module without `python_package` imported by a technical target → regenerated into the
  technical target, two classes. Mitigation: the toy sets `python_package` and TC-2 asserts identity;
  the docs say a value module imported across targets declares it (the existing cross-target rule).
- #302: `equals_string` on a multivalued slot → list of that one value (draw `st.lists(st.just(x))`
  via the existing multivalued wrapper; covered since `_scalar` is the item strategy).

## Delivery decisions

- **D-1.** `technical_classes` keeps its name and covers value classes.
- **D-2.** The holding rule reads the whole view (gate counterexample 1).
- **D-3.** No TypeScript across targets for value modules in this change (gate counterexample 4).
- **D-4.** #303 fallback location: `apply_defaults` (gate counterexample 6).
- **D-5.** #302's multivalued row may find no defect; then it stays as a regression test.
- **D-6.** A value module converted from UML gets no `python_package` from the converter; the docs
  say to add it when another target imports the module (gate counterexample 5, out of scope).
- **D-7.** The four stages run in parallel worktrees, each branched from `develop`, so no PR waits
  on another's merge. This change folder travels with PR 1 only; the lead records the other PRs'
  links and ticks in `tasks.md` on PR 1's branch. A clash in the toy's generated files is resolved
  at rebase by regenerating (P-0003).
- **D-8.** A value target's package is `<pkg>.domain.generated[.<group>]`, not
  `<pkg>.domain.<group>.generated` as first planned: the folder rule takes the segment right before
  `generated` as the layer and allows a group only after it. Kept the rule (other targets rely on
  it); the EPIC's outline, the spec delta and this design were corrected (builder's finding, task 1.3).
- **D-9.** The import rule for value modules checks direct imports, as the domain rule does; an
  indirect path through an unannotated module is not walked (review finding, consistent with the
  domain rule).
- **D-10.** Stage 1: `_mypy_targets` gave mypy both `domain/generated` and its nested
  `domain/generated/values`, which mypy refuses as a duplicate module; `_outermost_folders` keeps
  only the outermost of nested (and identical) folders. A general case once D-8 nests value packages.
- **D-11.** Stage 2 (supersedes D-4's location): the abstract root takes its kinds' identifier in
  `schema.give_identifier_to_abstract_roots`, run by `load_schema` (on a copy, the loaded module is
  never mutated) and by `apply_defaults`, so the runtime mapper reads it as the generators do (the
  review found the runtime view skipped `apply_defaults`). Kinds with different identifier slots
  raise `ValueError`; an abstract root with no kinds is left unchanged.
- **D-12.** Stage 2: GitNexus rates `load_schema` CRITICAL (23 direct callers, 115 in all). The new
  behaviour applies only to a schema with an abstract aggregate root; no toolkit artefact changed,
  the toy's shapes gained triples and lost none (graph diff), every suite is green. Flagged to the
  developer in the PR, as `slot-resolution` D-6 did.
- **D-13.** Stage 2: the toy's abstract class is `LendingItem`, not `Item` (a collaboration test
  defines its own `Item`); tests that used `Magazine` as a class the schema does not know now use
  `Gazette`.
- **D-14.** Stage 3: the multivalued case (#302) was a defect of the JSON-LD context, not of the
  strategy: the term's container came from the module-level slot, so framing returned one value.
  The context extension gives a class whose induced slot differs from the global one in
  `multivalued` a type-scoped term (JSON-LD 1.1, honoured by pyld), merged into any scoped context
  the stock generator already wrote; abstract classes and mixins are skipped. The fix also
  corrects the framed JSON the API serves for such a class. D-5's fallback did not apply.
- **D-15.** Stage 3: `Display.features` is `required` in its usage, so the draw always has it; the
  toy lock's entry for `Display`, new in the same unreleased commit, was set to `required` by hand
  (one line; `make generate` leaves it unchanged, the lock diff is additions only).
- **D-16.** Adding toy roots changes the route tables, the shape snapshot and the served OpenAPI
  golden: the hard-coded lists gained the new roots, the snapshot and golden were refreshed with
  their make targets (additions only).

## Review

One L2+L3 pass per stage (P-0005). Accepted and fixed:

- Stage 1: a stored root inheriting (is_a or mixin) a value class passed the holding rule
  (blocking; now `_held_ancestors`); E3/E10 table cleaned; design names `_never_stored_root_problems`;
  one `IMPORT_RULES` mapping; the folder hint only when a value module is present; identical mypy
  folders de-duplicated; a technical slot reported once. Declined: splitting `test_e1`'s three
  asserts (each has a message and one idea).
- Stage 2: the runtime view skipped the fix (blocking; D-11); several identifier slots raise; no
  kinds left as is; exact annotation compares; mixin and multivalued rows; LendingItem has no
  identifier property.
- Stage 3: the scoped term overwrote a stock scoped context (blocking; merged); induced slots in
  both directions; the stock class key (curie); plain test tables. Declined as out of scope: enum-
  and alias-specific scoped-term tests.
- Stage 4: `__all__` order fixed. Declined: calling `matched_version` through the top-level name
  (the names are the same objects, tested by identity; `negotiation`'s own tests cover behaviour).

## Delivery

Appetite MEDIUM, four stages: one PR each; each stage gets one L2+L3 review pass (P-0005), the full
review once at the end is waived as each stage is a separate small concern (stated in each PR). The
lead runs `make check-all` and `make test-containers` (only if an adapter changes: none planned) per
stage, GitNexus impact at stage start and before the last commit.
