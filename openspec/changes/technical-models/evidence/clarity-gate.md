# Clarity gate: technical-models (design.md + tasks.md)

No shaper self-score was recorded here; this is the first entry.

## run 1, 2026-11-17, 9.0/10, pass

Cold attack-and-gate run (full gate, 13 items, 6-criterion rubric). The attack's fixes were made
before scoring: `TOOLKIT_FOLDER` and segment-built paths (PD-1, task 1.2, TC-54); DEC-3 read as
"generated domain models", the hand-written `iris.py`/`tenant_move.py` imports made explicit (PD-2,
RISK-5, TC-53); the global slot `kind` collision (PD-9 `target_kind`, key `kind`); three testkit
records missed and `freshness.py` excluded from TC-50 (PD-11); term bundles combined with per-call
terms through `more` (PD-4, PD-5, TC-55); inclusive LinkML bounds against TC-26 and A-4's leeway
range (PD-6, TC-57); `ToolkitSettings()` holding `None` groups (PD-6 `default_instance`, TC-56,
TC-58); six wrong test file names.

Gaps left (small, folded or accepted under R-0005):

- `proposal.md` What Changes still lists nine testkit records and `GenerationTarget.kind`; the
  stage-4 reconciliation (P-0004) aligns it with PD-9 and PD-11.
- The module that holds the `default_instance` generation check is not named (a check under
  `generation/checks/`, as the other rules).
- TC-09 and TC-10 do not say how `lint-imports` runs on a scratch copy (a tmp tree with its own
  `.importlinter` and `root_package`, as the guard tests do with tmp trees).
- DEC-3's reading (hand-written domain modules may import technical models until
  `thematic-structure` DEC-3) awaits the developer; RISK-5 states the alternative.
- `generator-package` PD-1 disagrees with PD-11 on the testkit group's package and on
  `ConstraintCase`; RISK-7 records it for the developer.

## run 2, 2026-11-17, 9.0/10, pass

Delta run over the cross-change reconciliation (DEC-1..3; PD-1..3, PD-6, PD-7, PD-9, PD-11; error
matrix; RISK-5/7/8; tasks 1.2, 1.3, 3.3, 4.1; specs), checked against 48f80c6. Confirmed: the
importers of `domain.iris`/`domain.tenant_move` (94 test files; no domain module but
`tenant_move.py` imports `iris.py`), the 12 policy-free functions, `components.py:16`, the
`.importlinter` contracts, the guards' `generated` segment, `rp_generation.yaml:738/779/1040/1053/1157`,
`containers/fixtures.py:22-28`, the test file collision, PyJWT 2.15.1's algorithms, and the deny
pattern (refuses `none`, `NONE`, `HS*`, `hs512`; accepts `ML-DSA-44`, `EdDSA`) under the
generator's `fullmatch` validator. Stage order and TC ids consistent (1.2 before 1.3; TC-53..63
unique).

Fixed here: PD-2 named `iris.py:22-40`/`:244-253` as layout constants though they hold template
and alphabet constants too (now listed by name); "eleven wrappers over `DEFAULT_IRIS`" were ten,
and `tenant_resource_name`/`_resource_name` had no home (now in `services/iris.py`); `Iris`'s
imports of private layout names stated; `entrypoints/router.py` missing from the importer list;
`services.iris`/`services.tenant_move` must join `nothing-in-services-imports-the-bus` (PD-2,
task 1.2); task 1.3 deletes the old `domain/generated/service/`.

Gaps left, accepted (R-0005):

- The settings target's `shapes.ttl` carries a look-ahead `sh:pattern` SHACL cannot evaluate;
  recorded in PD-6, harmless while no shape validation runs over settings.
- Run 1's open items for the developer stand (proposal reconciliation P-0004 in PR 4; TC-09/10
  scratch-copy mechanics; RISK-7 coordination with `generator-package`).
