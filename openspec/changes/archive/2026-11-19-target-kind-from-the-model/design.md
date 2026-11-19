# PLAN (design): target-kind-from-the-model

Derives from the EPIC `target-kind-from-the-model` (`proposal.md`, DEC-1 to DEC-5).

## Context

On `develop` (df5a772): `GenerationTarget.target_kind` (alias `kind`, optional) is a slot of
`rdf_persistence_generation/model/rp_generation.yaml` (485-495), typed by the enum `TargetKind`
(949-962, whose descriptions say "as its `kind` key declares" and "every module of the target's
folder"). `steps._boundary_problems` (101-106) runs `target_kind_problems(view, folder, kind)` when a
kind is declared and `kind_folder_problems(folder, package, kind)` always; the latter returns early
for `kind is None` or a non-toolkit target (`boundary.py:256`), then exempts `FOLDER_EXEMPT`
(`rdf_persistence.testkit`, `rdf_persistence_generation`). `own_schemas(view, folder)` is the import
closure in the root's folder. Unknown keys of an entry are refused (`config.py`, extra input). All 20
toolkit targets declare a kind (1 `domain`, 19 `technical`); every module under `model/technical/**`
is `module_kind: technical`; `rp.yaml`'s folder holds unannotated and `access` modules.

## Goals / Non-Goals

Goals: DEC-1 to DEC-4. Non-goals: the EPIC's no-gos.

## Decisions

Declared in the EPIC; planning decisions:

- **PD-1 One function for the kind.** `derived_kind(view, folder) -> TargetKind` in
  `checks/boundary.py`: `TECHNICAL` if every schema of `own_schemas(view, folder)` is
  `module_kind: technical`, else `DOMAIN`. `steps._boundary_problems` calls it and passes the result
  to `kind_folder_problems` and `mixed_kind_problems`. `target_kind_problems` is deleted.
- **PD-2 No mixed target** (lead's choice, keeps today's check that `target_kind_problems` made for a
  declared domain target). `mixed_kind_problems(view, folder)`: when some but not all of
  `own_schemas` are `module_kind: technical`, fail with `"<target>: generates technical modules <m1,
  m2> beside domain ones: a target generates one kind"` — a target generates domain models or
  technical models, never both. When it reports, `kind_folder_problems` does not run (its "annotate
  them" hint would mislead). `<target>` in every message is the root schema's path as the generate
  output prints it. Rejected: accepting a mixed target
  as `domain` (it would let technical classes into a domain package unchecked).
- **PD-3 The folder rule for all.** `kind_folder_problems(folder, package, kind: TargetKind)` (no
  `None`): first the exempt packages pass; then a package without a `generated` segment, or with
  `generated` first (`package = "generated"`), fails "has no layer before `generated`"; then the
  layer must match the kind; then, only when `is_toolkit_schema`, the theme. Messages:
  `"<target>: package <p> has no layer before generated: a <kind> target's package ends in
  <layers>.generated"`; `"<target>: package <p> is not in a folder a <kind> target allows: <layers>
  before generated"`, adding for a derived `domain` in a technical layer `"; if its modules are
  technical, annotate them module_kind: technical"`; the theme message as today.
- **PD-4 The key goes.** The slot `target_kind` (485-495) is deleted from `rp_generation.yaml`, with
  its entry in `GenerationTarget`'s `slots` (35); the `BoundaryRule` value `target_kind` (943-946)
  is reworded "A target's modules are of one kind, derived from them, and its package sits in a folder
  that kind allows" — `mixed_kind_problems` and the folder problems both report under
  `BoundaryRule.TARGET_KIND`;
  `TargetKind`'s descriptions become "The kind of a generation target, derived from the modules it
  generates" and per value "every module it generates is `module_kind: technical`" / "not every
  one"; `make generate` regenerates `rdf_persistence_generation/generated/`. The extra-key refusal
  names `kind`. `pyproject.toml` loses its 20 `kind` lines.
- **PD-5 Our targets.**
  - The toy library: `package = "tests.fixtures.library.domain.generated"`, `python = "domain/generated"`,
    `diagrams = "domain/generated/diagrams"`; `tests/fixtures/library/domain/__init__.py` added (the
    folder is a package, as `generated/` is today); the old `generated/` deleted after `make generate`;
    `golden/` regenerated; the 63 files naming the package rewritten mechanically (ast-grep for imports,
    a text rename for strings); `Makefile:98,181` unchanged (they name the project file and the
    TypeScript folder).
  - The getting-started example: `package = "domain.generated"` (its `python` follows), a
    `domain/__init__.py` (a package, as for the toy library), its `library_app.py` lines 7-9 (`from
    domain import generated`, `from domain.generated import library`, `from domain.generated.library
    import Book`), and `tutorials/getting-started.adoc`. Its pin stays `tag = "v0.6.0"` until the 0.7.0 release PR moves
    it: 0.6.0 does not check folders, so the example is valid under both.
  - The cross-target fixture: `xt.a.domain.generated`, `xt.b.domain.generated`, and
    `tests/fixtures/cross_target/a/a.yaml`'s `python_package` likewise (its modules derive `domain`).
  - The generator tests' inline configs, by one rule: a domain project's package gains `.domain`
    before `generated` (`app.generated` → `app.domain.generated`, `proj.generated`,
    `partial.generated`, `project.generated` likewise; `app.generated.part` →
    `app.domain.generated.part`); a package with no `generated` segment gains `.domain.generated`
    (`p` → `p.domain.generated`, `app.a` → `app.a.domain.generated`, `a` → `a.domain.generated`); a
    project whose modules are technical uses `.services.generated`. Tests that assert the old
    behaviour are rewritten or deleted, each listed in task 1.1.

## Algorithm / approach

1. Tests first (task 1.1): the error matrix and TC-02's permanent form, red; the tests that encode
   the old rule rewritten or deleted.
2. PD-1 to PD-4 (task 1.2); green.
3. PD-5 in one commit with `make generate` (task 2.1); `make check-all`.
4. Docs and CHANGELOG (task 3.1).

### Anti-patterns

- Keeping `kind` as an optional, ignored key (a silent no-op).
- Exempting the toy library or the tests from the rule instead of moving them.
- Deriving the kind from every file of the folder rather than `own_schemas` (DEC-1's rejected option).
- Keeping `kind: TargetKind | None` and its `None` early return in `kind_folder_problems`.
- Running the theme check outside `is_toolkit_schema` (it would bind consumers to our themes).
- Renaming the 63 toy-library references by hand, apart from the regeneration.

## Error matrix

| Input | Expected |
|---|---|
| a consumer entry with `kind = "domain"` | refused, naming the unknown key `kind` |
| a consumer target of domain modules, `package = "app.generated"` | fails: no layer before `generated` |
| a consumer target, `package = "p"` | fails: no layer before `generated` |
| a consumer target, `package = "generated"` | fails: no layer before `generated` |
| a consumer target of domain modules, `package = "app.catalogue.domain.generated"` | passes; no theme check |
| a consumer target of technical modules, `package = "app.services.generated"` | passes |
| a consumer target of unannotated settings modules, `package = "app.services.generated"` | fails, derived `domain`; the message names the `module_kind: technical` annotation |
| a target whose own modules are some technical, some not | fails naming the target and the technical modules (PD-2) |
| a target whose only own module is `module_kind: access`, `package = "app.domain.generated"` | passes, derived `domain` |
| a toolkit target of technical modules, `package = "rdf_persistence.services.generated"` | fails: no theme before the layer |
| `rdf_persistence.testkit.generated`, `rdf_persistence_generation.generated` | pass (exempt) |

## Test cases

| ID | Input | Expected |
|---|---|---|
| TC-01a | the consumer rows of the error matrix | as stated, one unit test each (`test_boundary_check.py`) |
| TC-01b | the toolkit and exempt rows | as stated |
| TC-01c | the `kind` key | refused (`test_generate_config.py`) |
| TC-02 | the toolkit's 20 targets | before task 1.2, once: each derived kind equals its declared one; after, for good: `derived_kind` is `domain` for `rp.yaml` and `technical` for the other 19 (`test_boundary_check.py`) |
| TC-03 | the toy library, the getting-started example, the cross-target fixture | generate and pass in their new packages; `make test-containers` green |
| TC-04 | `/openapi.json`, toy TypeScript | unchanged but for paths |
| TC-05 | the feature `technical_models.feature` | its two kind scenarios rewritten to the spec's "a domain module in a technical target" and "a target without a kind"; green |

## Risks / Trade-offs

- **RISK-1 Consumers break on upgrade** (MWBv2). Likelihood high, impact low: each failure names the
  fix. Mitigation: the CHANGELOG migration note; MWBv2's upgrade is a change in its repo naming this
  one (D-12).
- **RISK-2 A derived kind differs from a declared one** in the toolkit. Likelihood low (all
  technical modules are annotated). Mitigation: TC-02's one-off form, before the key goes.

## Open Questions

None.

## Accepted gate

- **DEC-6** (developer, 2026-11-19, "yes accept both"): the PLAN proceeds below 9/10 (run 2: 8.7),
  with every gap run 2 listed fixed as the gate stated it (`evidence/clarity-gate.md`). PD-2 (no
  mixed target) is the lead's choice, open to the developer at review.

## Delivery decisions

- **D-1** (lead, task 1.2): "has no layer before `generated`" covers every package whose segment
  before `generated` is not one of `domain`, `services`, `adapters`, `entrypoints` (as the error
  matrix row `app.generated` requires), not only a missing or leading `generated`; a known layer of
  the wrong kind gets "is not in a folder a <kind> target allows". PD-3 read this way.
- **D-2** (lead, task 1.2): a mixed target's problem carries no element: the line is
  `[target_kind] generates technical modules <m> beside domain ones: …`, and the generate output
  names the target by its root schema, as PD-2's `<target>` requires.
- **D-3** (lead, task 2.1): tests that added a technical module to the domain toy (now a mixed
  target, PD-2) generate a separate technical-only project instead, keeping their intent.
- **D-4** (lead, review W1, re-labelled Critical): `user-manual/generate.adoc` says the check reads
  every schema of the entry's folder and that a folder of both kinds fails; DEC-1 derives the kind
  from the target's own modules only (its root's import closure in its folder). Re-labelled because
  the page is the migration guide every consumer reads for this breaking change, and it states the
  option DEC-1 rejected. Fix: the page says "the modules the target generates".
- **D-5** (lead, review W2, re-labelled Critical): the spec scenario "a consumer's settings without
  the annotation" has no test with an unannotated module; every fixture carries a `module_kind`.
  Re-labelled because a spec scenario without a test that fails on its regression is unverified.
  Fix: a module with no `annotations:` derives `domain`, and the boundary step on it with
  `app.services.generated` names `module_kind: technical`.
- **D-6** (lead, checker F1 and F2; developer: "go ahead, fix it"): the scenario map misses the
  spec scenarios "a domain target in an adapters folder" and "a consumer's own layout", and maps
  `test_a_technical_module_beside_a_domain_one_in_a_target_is_refused` only to the capability. Fix:
  a second row for each of the two covering tests, and that test re-mapped to "a target of both
  kinds". The cold read of the tutorial (12 points, none a path mismatch; one from this change: the
  page does not mention `domain/__init__.py`, which a namespace package makes optional) is a
  follow-up, not fixed here.
- Under the floor (review S1–S5, not fixed): S1 the feature scenario runs a consumer target where
  the spec's GIVEN says toolkit (planned in `tasks.md`); S2 the theme message does not name the
  derived kind (the scenario asks only target and package); S3 technical modules joined by `,`
  rather than `, `; S4 a redundant `TargetKind(kind)` in `kind_folder_problems`; S5 one `Then`
  asserts three things.
