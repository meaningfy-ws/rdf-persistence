> Derives from: EPIC `boundary-owned-hint` (proposal.md, issue #72). One stage, one PR into `develop`.
> Type: Implementation.

## 1. The message and the docs

- [ ] 1.1 Test first in `tests/unit/generation/test_boundary_check.py`; then PD-1. Gates:
  `make test-changed`, `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | technical module, `Terms.items` → `Term`, not owned | one REFERENCE problem; text contains `owned: true`, `Term inline` and `point the slot at a root, Principal or Activity` |
| TC-02 | same with `annotations: {owned: true}` | no REFERENCE problem |
| TC-03 | existing REFERENCE tests | still green (old text is a prefix) |

- [ ] 1.2 Docs (PD-2) in `architecture/generation.adoc`. Gate: `make check-docs`.

- [ ] 1.3 Close: `make check-all`; `openspec validate boundary-owned-hint --strict`; PR into
  `develop` closing #72; merge on green CI; archive the change.
