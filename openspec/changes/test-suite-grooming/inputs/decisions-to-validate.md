# Decisions to validate (taken while the owner was away)

Change `test-suite-grooming`, 2026-11-16/17. The owner accepted every audit proposal ("I accept
everything"), asked for local-first work, then left with the instruction to finish, commit, push
and merge without questions. These are the decisions the lead took on its own. Each says what was
done, why, and how to undo it.

## Process

1. **One pull request for the whole change** (design.md D-1), each stage a group of commits.
   Why: the stages were built in parallel worktrees on one branch. Undo: nothing to undo; the
   commits stay separable for a revert of any one stage.
2. **PR #131 (align-project-setup) merged** into `develop` after all its checks passed (the unit
   job took 32 min on GitHub's runner). Why: it was this change's base. Undo: `git revert -m 1`
   of its merge commit b3626cb.
3. **Review findings re-labelled Critical by the lead** (F-1 to F-8 in design.md, plus the final
   review's accepted list): each could lose a guard or data. Undo: none needed; they are fixes.

## Proposals not landed or landed partly

4. **P-2 (share the schema view) and P-4 (shared book triples): built, measured, NOT landed** (no
   saving within noise; P-2 would have changed a public API). Undo: the builds are described in
   design.md PD-2/PD-4 and can be redone; a profile of `ToyService()` is under *Debt*.
5. **P-51 kept two of its three pins**: no other test pins the namespace IRIs or the enum member
   counts (D-4). Undo: delete `test_the_plumbing_predicates_are_the_toolkit_namespace_ones` and
   `test_every_value_set_of_the_vocabulary_has_members` if you disagree.
6. **P-31 landed for the container tier only** (9 tests, not the report's "~25"); its unit half is
   under *Debt*. Undo: restore `[fake, garage]` with `git revert 64bb1c8`.
7. **Class 2 survivors chosen by mutation, not by "first N"** where they differed (D-3). Undo:
   none sensible; the dropped cases are in each commit's diff.

## Choices the PLAN left to the lead, or the code corrected

8. **`--dist loadgroup`** for the parallel lanes (65.7 s, against worksteal's 64.6 s, inside the
   3 % band; it keeps `xdist_group` usable). Undo: remove `--dist loadgroup` from the Makefile.
9. **`pytest-randomly` adopted, against the EPIC's no-go "no new test library beyond
   pytest-timeout and mutmut"**: PD-9 planned the trial and the adopt-on-green branch; two seeds
   ran green. Every lane runs in random order except `profile-tests` (`-p no:randomly`, for
   comparable timings). Undo: drop it from the `test` group and `make lock`.
10. **`assert_isomorphic` became a public testkit name** (F-8): a consumer-facing e2e test may use
    only public names. Undo: keep it private and copy a local helper into the e2e test.
11. **`polyfactory` dropped**, the deviation from checklist rule 6 written in
    `develop/testing.adoc`. Undo: add it back to the `test` group.
12. **The perf lane now needs Docker** (D-5): the store budgets moved there from the integration
    tier. Undo: move `tests/perf/store/*` back to `tests/integration/store/`.
13. **Two PLAN statements were wrong against the code** (D-6): settings are not frozen (the test
    asserts the minted IRI does not change), and the dump takes a clock (the test injects it).
    Undo: none; the tests now state the real contract.
14. **The timeout requirement is narrowed** to the parallel lanes (F-5): a thread timeout ends a
    serial session. Undo: switch to `timeout_method = signal` if serial lanes must survive a hang.

## Left open for you

15. **Spec question (DEC-5):** `rp-messages` says an empty commit spends a `Served` record;
    `test_messagebus_adversarial.py::test_an_empty_commit_does_not_spend_the_command_for_the_real_one_after_it`
    asserts the bus does not. Which is right? Nothing touching it changed.
16. **Debt** (design.md *Debt*): rule-5 monkeypatches with no fitting fake (a relay fake and a
    recording message bus would retire most), rule-12 waits with no injectable clock, P-20's rows
    outside its folders, two redundant production branches found by mutation (Fuseki `>= 500`; the
    bearer checks), the unit half of P-31.
17. **The 35 logic mutants of `domain/` that survive** are listed in the audit; raising the mutation
    score was a rabbit-hole of this change.

## Something you should know

18. **Another session used your main checkout** during the delivery (switching it to
    `docs/manual-revision-notes`). The lead moved to its own worktree (`temp/wt/lead`) and did not
    touch that checkout again; it is left as that session left it.
