# Decisions to validate (taken while the owner was away)

Change `test-suite-grooming`, 2026-11-16. The owner accepted every audit proposal ("I accept
everything"), asked for local-first work, then left with the instruction to finish, commit, push
and merge without questions. These are the decisions the lead took on its own; each says what was
done, why, and how to undo it.

## Process

1. **One pull request for the whole change** (design.md D-1), with each stage as a group of
   commits, instead of one PR per stage. The stages were built in parallel worktrees on one
   branch. Undo: none needed; the commits are separable.
2. **PR #131 (align-project-setup) merged** into `develop` after all its checks passed (the unit
   job took 32 min on GitHub's runner). It was the base of this change.
3. **Six review findings re-labelled Critical** by the lead (F-1 to F-6 in design.md): a tool that
   could erase the map, three merges that kept a weaker survivor, a spec delta that claimed more
   than the serial lanes give, a store check that could run first. Four suggestions were left
   "under the floor" (S4, S5, S7, S8).

## Proposals not landed or landed partly

4. **P-2 (share the schema view) and P-4 (shared book triples) were built, measured and NOT
   landed**: no saving within noise (design.md PD-2, PD-4). P-2 would have changed a public API
   for nothing. A profile of `ToyService()` set-up is under *Debt*.
5. **P-51 kept two of its three pins**: no other test pins the namespace IRIs or the enum member
   counts (D-4).
6. **P-31 landed for the container tier only** (9 tests, not the report's "~25"); its unit-tier
   half is under *Debt* (D-4).
7. **Class 2 survivors were chosen by mutation, not by the "first N" rule** where they differed
   (D-3): the first listed value often hit two guards.

## Choices the PLAN left to the lead or the code corrected

8. **`--dist loadgroup`** for the parallel lanes (65.7 s against worksteal's 64.6 s, within the
   3 % band; it keeps `xdist_group` usable).
9. **`pytest-randomly` adopted**: two seeds ran green; every lane now runs in random order.
10. **`polyfactory` dropped**, with the deviation from checklist rule 6 written in
    `develop/testing.adoc` (the named builders of `tests/toy.py` go through the models).
11. **The perf lane now needs Docker** (D-5): the store budgets moved there from the integration
    tier.
12. **Two PLAN statements were wrong against the code** (D-6): settings are not frozen (the test
    asserts the minted IRI does not change), and the dump takes a clock (the test injects it).
13. **The timeout requirement is narrowed** to the parallel lanes (F-5): a thread timeout ends a
    serial session.

## Left open for you

14. **Spec question (DEC-5):** `rp-messages` says an empty commit spends a `Served` record;
    `test_messagebus_adversarial.py::test_an_empty_commit_does_not_spend_the_command_for_the_real_one_after_it`
    asserts the bus does not. Which is right? Nothing touching it changed.
15. **Debt** (design.md *Debt*): rule-5 monkeypatches with no fitting fake (a relay fake and a
    recording message bus would retire most), rule-12 waits with no injectable clock, P-20's
    rows outside its folders, two redundant production branches found by mutation (Fuseki
    `>= 500`; the bearer checks), and the unit half of P-31.
16. **The 35 logic mutants of `domain/` that survive** are listed in the audit; raising the
    mutation score was a rabbit-hole of this change.

## Something you should know

17. **Another session used the main checkout** during the delivery (switching it to
    `docs/manual-revision-notes`). The lead moved to its own worktree (`temp/wt/lead`) and did not
    touch that checkout again.
