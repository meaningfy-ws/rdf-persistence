---
kind: rule
id: P-0012
type: constraint
strength: default
status: active
scope:
  - activity:writing
when: documentation covers behaviour that a specification of record states
do: summarise it and link to the specification
instead_of: restating its requirements
because: two copies of a requirement drift; the specs are the truth
source: 2026-11-19 'yes summarise and link, no redundancy'
added: 2026-11-19
approved: 2026-11-19
last_confirmed: 2026-11-19
private: false
---
