EPIC: narrowed-slot-followups (proposal.md, issue #428). Decisions: design.md PD-1 to PD-3, DEC-1 to DEC-3.

> Derives from: EPIC `narrowed-slot-followups`. One stage (TINY), one pull request.

Every task: the failing test first (for a test of working code, the mutation of design.md PD-2,
reverted before green), in the tier named; narrow check `uv run pytest <file>` and `make lint`;
task gate `make test-changed check-quality`; commit body `Refs: narrowed-slot-followups <task>
<PD>`. Builders never commit; the lead does. No existing test is moved; every new test runs in the
lane of its folder (`make test-generator`).

## 1. Stage 1: the four findings of #428

- [x] 1.1 Lead: `uv sync --all-extras` in the worktree (D-1), `make reindex`; `openspec validate
  narrowed-slot-followups --strict` passes, and the MODIFIED requirement differs from
  `openspec/specs/rp-generation/spec.md` only in its unique-key sentence and the new scenario.
- [x] 1.2 Unit, W1 and S2a (T-W1, T-S2a). In `tests/generator/unit/test_ext_pydantic_split.py`,
  the five rows `class-not-under`, `uri-against-string`, `class-against-type`,
  `type-against-class`, `class-against-enum` (all marked) in
  `test_a_field_overriding_a_slot_incompatibly_carries_a_type_ignore_and_only_then`, and
  `test_an_identifier_or_key_slot_is_never_marked` (params `identifier`, `key`). Red: the three
  `_is_under` breaks and the guard break of design.md's test plan, each failing its rows. Accept:
  all pass with `pydantic_split.py` unchanged (`git diff` empty for it).
- [x] 1.3 Integration, W2 and S2b (T-W2, T-S2b), parallel to 1.2. In
  `tests/generator/integration/test_generated_code_imports.py`: TC-1 gains `SubPart`, the
  `range: SubPart` narrowing, and the covariant `main_part` / `SubPiece` override with its
  no-mark assertion; TC-4 gains `OptionalOneKeyedHolder` built without `parts`. Red: the breaks
  of design.md's test plan. Accept: both pass, mypy clean; any substitute class (RISK-2) is
  named in the report.
- [x] 1.4 Integration, S1 (T-S1, PD-1), after 1.2 and 1.3. First, failing:
  `test_a_keyed_slot_rendered_as_a_dict_checks_its_values` fails with `AttributeError` on `{}`
  (if its `dict` annotation assertion fails instead, stop: RISK-1). Then the loop line of
  `unique_keys_validator.py.jinja` (PD-1) and the golden file
  `tests/fixtures/library/golden/pydantic_validators/validators.py.golden` (compared by
  `tests/generator/unit/test_ext_pydantic_validators.py`). The lead runs
  `make generate` (D-2) before the green run. Accept: T-S1, TC-4 and the golden test pass;
  `make check-generated` shows only the three validators' loop lines and the manifests (RISK-3).
- [x] 1.5 Docs (PD-3): `CHANGELOG.md` `[Unreleased]` *Fixed*; scenario-map rows for the new tests
  in `tests/audit/scenario-map.csv` (T-S1 against the new scenario). Accept: `make check-docs`
  passes.
- [ ] 1.6 Lead: `make check-all`; one review pass (TINY); each spec scenario shown in
  `evidence/acceptance.md`; #428 closed by the PR.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [ ] 1.6
  (1.2 and 1.3 run in parallel after 1.1; 1.4 regenerates, so it runs alone after them.)

## Verification

`make check-all` green; `openspec validate narrowed-slot-followups --strict`; the clarity gate
logged in `evidence/clarity-gate.md`.
