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
