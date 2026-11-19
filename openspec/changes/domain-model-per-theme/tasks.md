> Derives from: EPIC `domain-model-per-theme` (proposal.md, DEC-1 to DEC-8)

One stage, one PR (MEDIUM), after `target-kind-from-the-model` is merged. Checked at shaping (lead,
on develop 2f75a60+): every hand-written and generated importer of `rp_access`/`rp_tenancy` is in
`access` or above; of `rp_provenance`/`rp_files`, in `provenance`/`files` or above; of the
collaboration modules, in `collaboration` or above — except `schema` (task 1.1).

## 1. Before the move

- [x] 1.1 PD-8 (DEC-6): `schema` reads the stored-file class and the tenant-state IRIs from the
  SchemaView; no import of `rp_files`/`rp_tenancy` from `schema`. Test first. Gate:
  `make test-changed check-quality`.
- [x] 1.2 PD-1 to PD-5 in the generator, test first: TC-06 with its fixture. Prove the `access` target
  (`rp_tenancy.yaml` → `rdf_persistence.access.domain.generated`) end to end in a scratch copy
  (RISK-3). Gate: `make test-generator`.

## 2. The move

- [ ] 2.1 PD-6, PD-7, PD-9 (DEC-1 to DEC-5) in one commit: `rp_collaboration.yaml`, the annotations,
  the four entries, the three `domain/__init__.py`, `make generate`, the eager imports of
  `rdf_persistence/__init__.py`, the deep imports, the guards, `themes-ordered`. TC-01 to TC-05, TC-07.
  Gate: `make test-fast check-quality`.

## 3. Docs and release note

- [ ] 3.1 `architecture/index.adoc#themes` (the domain packages per theme),
  `architecture/models.adoc` (the diagrams stay one set, from `rp.yaml`),
  `architecture/generation.adoc#cross-target` (the import beside the root, the two module sets, the
  combined artefacts); CHANGELOG `[Unreleased]` Changed, BREAKING, with every moved path
  (DEC-8). TC-08. `make check-docs`.

## Roadmap

- [x] 1.1 · [x] 1.2 · [ ] 2.1 · [ ] 3.1

## Verification

`make check-all`, `make test-containers`, `make check-spec`, `make refresh-map` green on the PR's
commit; TC-01 to TC-08; clarity gate ≥ 9/10 (`evidence/clarity-gate.md`).
