---
kind: rule
id: P-0021
type: default-with-exception
strength: default
status: active
scope:
  - activity:delivery
when: merging a PR while the owner has suspended GitHub CI (until the owner says CI is back)
do: do not wait for GitHub CI checks; merge on a passing local make check-all (the repository's full local gate) and record that local result in the PR
instead_of: waiting for green GitHub CI
exception_of: P-0013
because: a GitHub billing issue stops CI; the owner relies on local tests until they say otherwise
source: 2026-11-24 'lets stop waiting for CIs in Github, lets rely on passing tests locally, okay ? move on, do not wait anymore on CIs untill I tell you. there is a billing issue with GH today.'
added: 2026-11-24
approved: 2026-11-24
last_confirmed: 2026-11-24
private: false
---
