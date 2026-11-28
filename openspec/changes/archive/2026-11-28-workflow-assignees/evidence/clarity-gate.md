# Clarity gate: workflow-assignees

Full gate on `design.md` + `tasks.md`, run by a fresh reader after the adversarial attack (12
counterexamples, all folded into the PLAN on 2026-11-27).

- run 1, 2026-11-27, 8.6/10, fail (gaps: spec vs D-3 on no workflow; shared helper file unnamed;
  D-7 without fallback; `design.md` over the MEDIUM budget; missing anchors and full paths)
- run 2, 2026-11-27, 9.1/10, pass (gaps 1, 2, 3, 5 closed; gap 4, the size, left open)

Accepted: gap 4 (`design.md` 21.5 KB against a 12 KB MEDIUM budget), kept for the error matrix and
the attack's findings; no `DEC-` needed, the gate passed.

Scenario sign-off: the developer signed off every scenario of `specs/rp-workflow/spec.md`,
2026-11-27, the two the attack added included.
