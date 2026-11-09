<!-- SECONDARY seed record — preserved, never groomed. The EPIC (proposal.md) supersedes it. -->

# Seeds: issues #42, #43, #44, #45 (mapping-workbench-v2 adoption, 2026-11-08)

All four were filed by the mapping-workbench-v2 (MWB2) team, which locks rdf-persistence
`develop` at `f38a11ac`. Full texts: GitHub issues #42–#45. Each claim was checked against the
code on 2026-11-09:

| Issue | Claim | Checked |
|---|---|---|
| #42 | No `py.typed`; consumers' mypy reports `import-untyped` | `rdf_persistence/py.typed` absent; build backend `uv_build` |
| #43 | Tenant DELETE and aggregate DELETE share `Action.DELETE` | `entrypoints/router.py:259` and `:321` |
| #44 | `rename` updates the access record only; root label goes stale | `services/tenancy.py` `rename` (~l.243); `create` copies the label into the root |
| #45 | adopt.adoc step 6 imports testkit submodules that `assert_public_imports` refuses | `testkit/__init__.py` exports none of guards, conformance, roundtrip, strategies, shape_snapshot, model_shape |

Also seen: #24 and #25 are still open but were delivered (archive `2026-11-08-testkit-wait-until`,
`2026-11-08-generation-fix-hint`); they only need closing.

## Questions and developer's answers (2026-11-09)

- **Q-1 (#43)** How is deleting the tenant itself guarded? → **Require `administer`** on the tenant
  (BREAKING for roles holding `delete` without `administer`). Rejected: a `tenant_delete_action`
  setting on `ServiceSettings`.
- **Q-2 (#44)** How are the two label copies kept equal? → **Rename writes both**; `PUT` on the root
  refuses a label different from the record's. Root written first, record last; a failure between
  them is repaired by retrying the rename. Rejected: derive the label when served; `PUT` on the root
  renaming the tenant.
- **Q-3 (#45)** Which side changes? → **Export the guard API from `rdf_persistence.testkit`**,
  lazily where heavy; step 6 imports only top-level names. Rejected: an allow-list of documented
  testkit modules in `assert_public_imports`.
- **Q-4** Packaging? → **One SMALL EPIC**, one stage, one PR closing #42–#45.
