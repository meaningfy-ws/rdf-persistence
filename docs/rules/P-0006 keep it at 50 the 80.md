---
kind: rule
id: P-0006
type: parameter
strength: default
status: active
scope:
  - activity:coding
when: setting or reviewing the coverage floor of the feature tests (make test-feature)
do: keep it at 50 %; the 80 % floor applies to the unit lane and to make test
slot: feature-coverage-floor
value: 50 %
because: the owner's stated preference
source: "2026-11-16: 'for features it is fine to stay at 50%'"
added: 2026-11-16
approved: 2026-11-16
last_confirmed: 2026-11-16
private: false
---
