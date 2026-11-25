---
kind: rule
id: P-0023
type: preference
strength: default
status: active
scope:
  - activity:delivery
when: a make test-seed run passed on the commit the lead is gating
do: take its pass as the unit and feature result; do not run make test-unit or make test-feature on their own, and check the coverage floors with make check-all
instead_of: running the unit and feature lanes again after the seed
because: the seed already ran every unit and feature test once; a second run costs minutes of a shared queue for no new result
source: 2026-11-25 'yes stop test-unit, use the seed'
added: 2026-11-25
approved: 2026-11-25
last_confirmed: 2026-11-25
private: false
---
