<!-- Secondary input, never groomed. Q&A record of the shaping session of 2026-11-20. -->

# Q&A: shaping the consumer's toolkit needs (2026-11-20)

## Consumer triage (MWB2, pasted by the owner)

#196 then #199 are necessary and sufficient now: with both merged, MWB2 `v2-02` closes and `v2-03`
starts. #201 and #198 before `v2-03`'s last stage; #202 before `v2-04` stage C and `v2-05`; #203
before `v2-05`'s search task; #204 not needed now; #197, #200, #189, #192 block nothing. `v2-05`'s
fragment key relies on the tagged-value rule (#196, comment 1, rule 17), so the converter must cover
it.

Owner's brief: "the smallest epics that can address all these issues; as small interventions as
possible, as fast as possible".

## Questions and answers

1. **Q:** May an application aggregate root be `is_a: Activity`? **A:** allow it, after a spike
   (recommended option). → DEC-4.
2. **Q:** The rule table grew through four comments while the domain expert reviews the UML; freeze
   it now, or keep it open? **A:** "Stay open until stage 2": new rules are accepted until stage 2
   starts, then frozen. → DEC-5.
3. XMI was not asked: the issue states a `.qea`-only first version unblocks the consumer. → DEC-1,
   no-go.

## Round 2 (2026-11-20)

The planner's open questions on the PLAN (design.md, then OPEN-1..OPEN-9), each with a recommended
default. **Owner's answer: accept all recommendations**, including the rewording of the spec
scenario on toolkit-filled slots. Recorded as design.md PD-26..PD-34.

1. **Q:** The scenario "a root that is an activity" makes `started_at_time` required, which the
   toolkit-filled rule refuses. **A:** drop the `required`, report it, reword the scenario. → PD-26
2. **Q:** If cyclic module imports break generation? **A:** merge each cycle's packages into one
   module. → PD-27
3. **Q:** Elements without a note? **A:** no placeholder; one `no-note` report line each. → PD-28
4. **Q:** An `rp_unlabelled` part ("neither label slot")? **A:** `Described` only, no `Tracked`.
   → PD-29
5. **Q:** Two or more domain parents? **A:** fail the run. → PD-30
6. **Q:** Unknown class stereotypes? **A:** fail; pass them with `--not-generated` or bring a rule
   before the freeze. → PD-31
7. **Q:** Missing multiplicity? **A:** fail, not UML's default `1`. → PD-32
8. **Q:** Composite orientation? **A:** only `SourceIsAggregate=2` until an EA sample is supplied.
   → PD-33
9. **Q:** Where does SPIKE-1's `Review` live? **A:** in the toy, permanently. → PD-34

Gate: a fresh reviewer scored the PLAN 8.8/10; the owner's rule R-0005 accepts it, gaps folded.
