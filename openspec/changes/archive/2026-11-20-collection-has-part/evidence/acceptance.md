# Acceptance: collection-has-part

2026-11-20. The demo was skipped: the developer accepted the change without it ("skip the acceptance
demo, i accept it"). SMALL appetite. What stands in for it:
- IT-1 on Fuseki: the toolkit's 2 → 3 restates a stored shelf's members with `dcterms:hasPart`.
- TC-7: a saved collection states `dct:hasPart`, and every service finds its members.
- TC-10: a dump at version 2 is restored, and `members` lists the members.
- Both full-gates runs on PR #207 passed.
