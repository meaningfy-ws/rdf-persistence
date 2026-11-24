# Q&A record: generator-module-cycles (secondary; never groomed)

The planner ran as a subagent and could not ask; the questions below go to the owner as one round.
Each carries a recommendation and the default the PLAN assumes now: the PLAN is complete under the
recommended answers. Owner rules applied: R-0002 (risk questions from this task's own context),
R-0003 (how the work succeeds or fails and how it is checked, test-first), R-0005 (8.8 acceptable).

## Decided by the planner within the brief (not asked)

| Question | Decision | Why | → |
|---|---|---|---|
| Which of #208's two fixes? | lazy imports + completion in `__init__.py` | probe P-2 works in any import order with mypy strict; one module per component would move classes and rebuild the converter's merge in the generator | DEC-1 |
| Touch modules in no cycle? | no, byte-identical | no regenerated diff anywhere | DEC-2 |
| A cycle Python cannot load? | refused, naming modules and classes | no load order exists; a merge would move classes silently | DEC-3 |
| Does #206 fit this appetite? | no | different check and code (`checks/`), its own undecided rule (identifier slots), and it would refuse the converter's golden output today (probe P-3) | DEC-5, OPEN-1 |
| One PR or two? | two stages | stage 1 is independent of the converter and can land while `converter-hardening` works on `uml/` | DEC-6 |
| Converter rule on kinds of merged packages | removed; `rp-generate`'s boundary check refuses a domain module importing an access one | the rule only existed because of the merge | DEC-4 |

## Open questions for the owner

### OPEN-1: where does #206 (two slots on one `slot_uri`) go?
- Asked because: the brief allows it here "only if it fits"; it does not (DEC-5), so it needs a
  home.
- Recommendation: its own TINY EPIC in the generator's checks, after this one, with identifier
  slots exempt (an identifier is written as `@id`, never as a predicate, so the converter's
  `identifier` on `dcterms:identifier` beside `id` is no clash).
- PLAN default: #206 is a no-go here and stays open.

### OPEN-2: inheritance both ways between two UML packages
- Asked because: today the merge makes such a model generate; after stage 2 `rp-generate` refuses
  it (DEC-3, RISK-1), and whether the consumer's model has one is unknown.
- Recommendation: refuse, with the conventions page saying how to fix the model (move the classes
  into one package); task 2.6 asks the consumer to run its model on the stage 2 branch first. If it
  is refused there, bring it back to the owner before merging rather than keep a narrow merge.
- PLAN default: no merge of any kind in the converter.

### OPEN-3: order against `converter-hardening`
- Asked because: both EPICs edit `uml/convert.py` (`_settle`, `Layout`, `_module_kinds`); #229
  asks to move the import-graph code out of `convert.py` (RISK-5).
- Recommendation: stage 2 of this EPIC merges before `converter-hardening` starts its #229
  structure items; `converter-hardening`'s other items (#258-#261) are free to run in parallel.
- PLAN default: as recommended; if `converter-hardening` lands first, stage 2 rebases on it.

### OPEN-4: the BREAKING converter output
- Asked because: a consumer that already converted a cyclic model gets one module per package on
  its next conversion, and the classes of the later packages move module (DEC-4, RISK-3).
- Recommendation: accept, with the `CHANGELOG.md` **BREAKING** entry; release it in the next minor
  version (pre-1.0) with the converter's other changes.
- PLAN default: as recommended.

## Question round parked (2026-11-22)

The owner parked the question round: the OPEN items above are unanswered. The PLAN stands
under the recommended answers; nothing is decided until the owner answers.

## Delivery start (2026-11-24)

The owner asked the lead to deliver this PLAN after rebasing it on `develop`. Checked against
`develop` after `converter-hardening` (#349, archived 2026-11-24): every symbol the PLAN names in
`uml/` and `extensions/pydantic_split.py` is still there, the `rp-uml-import` delta differs from
the live requirement only by its intended changes, and only line references moved (fixed). OPEN-3
is settled by events: `converter-hardening` landed first and did not move the import-graph code,
so stage 2 starts on it, as the PLAN's default says. OPEN-1, OPEN-2 and OPEN-4 proceed under their
recommended answers (R-0007), shown to the owner at the end. Added: RISK-6 in design.md, the
owner's request to re-run converter-hardening's RISK-4 check on a cyclic pair (task 2.4).
