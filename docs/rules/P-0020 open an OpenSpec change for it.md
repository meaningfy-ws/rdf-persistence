---
kind: rule
id: P-0020
type: procedure
strength: default
status: active
scope:
  - activity:coding
when: a bug fix, or a group of related bug fixes, is requested
do: open an OpenSpec change for it first (EPIC with its PLAN, sized TINY or SMALL), fix the bug under it, then reconcile and archive it; record a change retrospectively only when the work was already done without one
because: "no work happens without an EPIC change: the spine must hold every decision and the specs must gain what a fix adds"
source: 2026-11-22 'approve 1, but try to avoid doing work withoit an epic change, so better open epic chnages for bug fixes (or groups of bugfixes) when a bugfix is requested then create an epic change for it, and then fix it, and close it.'
added: 2026-11-22
approved: 2026-11-22
last_confirmed: 2026-11-22
private: false
---
