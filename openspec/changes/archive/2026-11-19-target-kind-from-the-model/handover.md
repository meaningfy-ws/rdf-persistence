# Hand-over: target-kind-from-the-model, after stage 1 (the last)

## Done
Stage 1 (tasks 1.1 to 3.1), PR #188, merged by the watch-and-merge command after this note.
Gates on fb973944: `make check-all` (7313 + 97 + 1034 passed), `make check-spec`, `make refresh-map`
green; `make test-containers` (314 passed) green on 2730d72a, which has the same code (after it,
only the scenario map and this folder changed). One L2+L3 review pass (7 findings, 2 fixed), the
checker (F1 and F2 fixed as D-6), a cold read of the tutorial. Acceptance demo waived
(`evidence/acceptance.md`); no docs owed (`evidence/docs-owed.md`); proposal reconciled (P-0004);
the change archived.

## Decided since the PLAN
D-1 to D-6 (design.md, Delivery decisions).

## Open
- Review S1 to S5, under the floor (design.md). S2: the theme message does not name the derived
  kind, which the requirement's SHALL literally asks for.
- The cold read of `tutorials/getting-started.adoc`: 12 points, none a path mismatch. One comes
  from this change: the page does not mention `domain/__init__.py`. A follow-up for a docs pass.
- Six config-parsing tests keep layer-less packages (`test_freshness.py:343,365`,
  `test_generate_config.py:68,87,89`, `test_generation_inputs.py:82`). They never run the boundary
  step.

## Next
`domain-model-per-theme` (its own handover.md). The 0.7.0 release comes after both changes
(DEC-5, DEC-8 there); that release moves the getting-started pin off `v0.6.0`.

## Prompt
Act as the team lead (epic-delivery). Deliver openspec/changes/domain-model-per-theme from its
handover.md.
