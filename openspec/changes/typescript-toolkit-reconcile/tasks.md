EPIC: typescript-toolkit-reconcile (proposal.md). Decisions: DEC-1 to DEC-5, design.md PD-1 to PD-3.

## 1. One stage — branch `change/reconcile-typescript-toolkit-modules`, one PR

- [ ] 1.1 **toy + tests** — PD-1, PD-2; TC-1 to TC-4. Tests first (PD-2), then the toy slot and
  `make generate` in this worktree (only this builder runs it). Accept: new tests pass; the technical
  tree imports a toolkit type from the owner's folder; the domain tree is byte-identical;
  `make typecheck-ts` passes; task gate green.
- [ ] 1.2 **docs** — PD-3 (side by side with 1.1, disjoint files). Accept: `make check-docs` green.
- [ ] 1.3 **lead** — scenario-map rows (TC-1 to TC-5); `make check-all`; one review pass (SMALL);
  PR into `develop`; merged on green CI; archive.

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 (1.1 and 1.2 side by side)
