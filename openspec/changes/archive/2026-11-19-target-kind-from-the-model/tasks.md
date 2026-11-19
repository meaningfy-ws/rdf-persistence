> Derives from: EPIC `target-kind-from-the-model` (proposal.md, DEC-1 to DEC-5)

One stage, one PR (SMALL).

## 1. The derived kind and the rule for every target

- [x] 1.1 Tests first, red: TC-01a to TC-01c, TC-02 (both forms), TC-05. Rewrite or delete the tests
  of the old rule:
  - `tests/generator/unit/test_boundary_check.py`: `kind_problems_of` and its tests (438-475) deleted
    (PD-1); the `TargetKind | None` calls (464, 533-705) pass a kind; the consumer case at 638
    (`app.generated` passes) inverted to the matrix row.
  - `tests/generator/unit/test_technical_exemption_adversarial.py` (11, 140-143): the kind argument.
  - `tests/generator/unit/test_generate_config.py` (120, 125, 151, 217): the `kind` alias tests become
    TC-01c.
  - `tests/generator/unit/test_ext_jsonld_context.py:254`: the assertion that `target_kind` is in the
    context, deleted with the slot.
  - `tests/generator/unit/test_generate_config.py:143-148` (a kind-literal test): deleted.
  - `tests/generator/unit/test_python_package_rule.py:50`: the `kind = "domain"` line dropped.
  - `tests/generator/unit/test_default_instance_generate_adversarial.py:57`: `kind = "technical"`
    dropped; its package becomes `proj.services.generated`.
  - `tests/generator/integration/test_getting_started_example.py:19`: `PROJECT_MODULES` becomes
    `("library_app", "domain")`.
  - `tests/feature/technical_models.feature` (28-40) and `tests/feature/test_technical_models.py`
    (206-240): TC-05. The kind scenario becomes: "Given a copy of the toy library whose package is
    `tests.fixtures.library.services.generated`; When it is generated; Then generation fails naming
    the package and the derived kind `domain`".
  - `tests/audit/scenario-map.csv`: every row naming `A target declares the kind of model it
    generates` (30 rows: 390-400, 3884-3885, 3900-3903, 4185-4192, 4311-4312, 4348) re-keyed to `A
    target's kind is derived from its modules`; rows added for the new and renamed tests, so
    `make refresh-map` exits 0.
- [x] 1.2 PD-1 to PD-4: `derived_kind`, `mixed_kind_problems`, `kind_folder_problems` for every target,
  `target_kind_problems` and the `target_kind` slot deleted, `TargetKind` reworded, the 20 `kind`
  lines removed from `pyproject.toml`; `make generate`. Gate: `make test-changed check-quality`.

## 2. Our own targets

- [x] 2.1 PD-5 in one commit with `make generate`: the toy library (package, `python`, `diagrams`,
  `domain/__init__.py`, the old `generated/` and `golden/`, the 63 references), the getting-started
  example (`pyproject.toml`, `library_app.py`), the cross-target fixture (`pyproject.toml`,
  `a/a.yaml`), the generator tests' inline configs by PD-5's rule. TC-03, TC-04. Gate:
  `make test-fast check-quality`.

## 3. Docs and release note

- [x] 3.1 Each page, and what it becomes:
  - `architecture/generation.adoc` (308, 381-407, 447): "The `kind` key" becomes "The kind of a target"
    (derived, no mixed target, the folder rule for every target, the theme rule for the toolkit);
    "a consumer keeps its own layout" goes.
  - `architecture/index.adoc` (431-432): the link and the words "The `kind` key" follow the renamed
    section.
  - `develop/generator.adoc:80`: `target_kind_problems` becomes `derived_kind` and
    `mixed_kind_problems`.
  - `user-manual/generate.adoc` (44, 186-224): the entry keys without `kind`; the example package
    `library.technical.generated` becomes `library.services.generated`; the sample output and the
    "cannot take a `kind`" paragraph (222-224, which says a folder of both kinds may leave the key
    out) replaced by the folder rule, its failure, and the failure of a target of both kinds (PD-2).
  - `tutorials/getting-started.adoc`: line 93 "into `generated/`" becomes `domain/generated/`; lines
    164-165 ("rather than the flat `generated/` of this tutorial") deleted.
  - CHANGELOG `[Unreleased]` Changed, BREAKING, with the migration note (DEC-5).

  `make check-docs`.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 2.1 · [x] 3.1

## Verification

`make check-all`, `make test-containers`, `make check-spec`, `make refresh-map` green on the PR's
commit; TC-01 to TC-05; clarity gate ≥ 9/10 (`evidence/clarity-gate.md`).
