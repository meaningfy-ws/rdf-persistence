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

## Re-shape, 2026-11-09 (later the same day): issues #46 to #51

While #42–#45 were being shaped, MWB2 filed six more issues (full texts on GitHub). Checked
against the code at `f38a11a`:

| Issue | Claim | Checked |
|---|---|---|
| #46 | `Iris` takes an `id_source`, `install_service` cannot pass one | `domain/iris.py` ~l.339; `entrypoints/kit.py:62` builds `Iris(settings, *iri_types(view))` |
| #47 | No TypeScript for the service's wire types; `rp_service` not importable | `services/schema.py` `metamodel_importmap` globs `model/*.yaml` only; `pydantic_split` refuses modules outside `model/` |
| #48 | Ownership rule refuses non-root classes even in a `technical` module | `generation/checks/boundary.py` `_ownership_problems` ignores the module kind |
| #49 | No consumer hook on the generic grants/root/label writes | `services/tenancy.py` `set_grants`, `rename`; `aggregates.py` `replace`. The `If-Match` write is a conditional update then an ASK (`session.py` `replace_graph`), so check-then-write under one version is atomic |
| #50 | A `modify`-only role cannot read the record version a rename needs | the version is served only by `GET …/grants` (`administer`) |
| #51 | No read tells the caller its permitted actions | `AccessRules.may` exists; no response uses it |

Also found: `InvalidBody` maps to **422**, not 400 (`entrypoints/problems.py:36`); PD-3 corrected.

### Questions and developer's answers (round 2)

- **Q-5** Packaging of #46–#51? → **One big EPIC**: `mwb2-adoption-fixes` grows to ten issues,
  delivered in stages. Rejected: folding only #50/#46 and three new EPICs; one EPIC per issue.
- **Q-6 (#50)** → **`Record-ETag` header on the tenant root read**; DEC-2 unchanged. Rejected: one
  combined label+root edit under one version.
- **Q-7 (#49)** → **Validators passed to `install_service`**, run inside the write after the
  version check. Rejected: unmounting the generic routes; both.
- **Q-8 (#51)** → **A response header on document reads, and an `allowed_actions` slot on
  `TenantSummary`**. Rejected: a field in every body; deferring.
- **Not asked, planner's decision (flagged to the developer for veto):** #47 is met by `rp-generate`
  writing `rp_service.ts` (DEC-8), because making `rp_service` importable would also need the
  Python generator to map a second metamodel folder; #46 follows the issue's own proposal (DEC-7);
  #48 follows the issue's own proposal (DEC-9).
