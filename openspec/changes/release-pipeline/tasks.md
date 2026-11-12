> Derives from: EPIC `release-pipeline` (proposal.md). One stage, one PR into `develop`
> (`ci/release-pipeline`), then the first release (0.2.0) by the pipeline itself (PD-9).
> Type: Implementation.

The workflow cannot be unit-tested; it is proved by a release-please dry run before merge (1.3) and
by the real 0.2.0 run after it (3.1). Code changes are test-first.

## 1. Version source and release-please

- [ ] 1.1 Test first, in `tests/unit/test_smoke.py`: TC-01. Then PD-2: delete `VERSION`; in
  `rdf_persistence/__init__.py` set `__version__` from `importlib.metadata.version("rdf-persistence")`;
  in `pyproject.toml` replace the comment "The single source of truth for the version is the root
  VERSION file; keep the `version` field below in sync." with "The version lives here alone;
  release-please bumps it (never edit it by hand)." Gates: `make test-changed`,
  `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `rdf_persistence.__version__` and `tomllib.load(pyproject.toml)["project"]["version"]` | equal and non-empty |

- [ ] 1.2 Add `release-please-config.json` exactly as in design.md "Algorithm / approach" and
  `.release-please-manifest.json` = `{".": "0.1.0"}`. In `.github/workflows/release.yaml` (PD-1,
  PD-5, PD-6, PD-10): rewrite the header comment (no PyPI; what each job does; points to
  `develop/index.adoc#release`); `concurrency`; the action gets `config-file`, `manifest-file`,
  `target-branch: develop` and no `release-type`; outputs `released`, `tag`, `version`;
  `build` job (`needs: release-please`; checkout, `astral-sh/setup-uv@v6`, `uv build`, the two
  checks of PD-6 as plain `test`/`grep -x` shell lines, `gh release upload "$TAG" dist/* --clobber`
  with `GH_TOKEN`); no `main` job (PD-1: `main` is moved by hand; the header comment says so);
  delete `testpypi`, `pypi` and `id-token`. Check: `uv build` locally and run the two PD-6 checks by
  hand against `dist/` with `VERSION=0.1.0` (record the output); `uv run pre-commit run --files
  .github/workflows/release.yaml release-please-config.json .release-please-manifest.json` if
  pre-commit has YAML/JSON hooks.

- [ ] 1.3 Dry run (attack, read-only): push the branch, then
  `npx -y release-please@17 release-pr --dry-run --token "$(gh auth token)"
  --repo-url meaningfy-ws/rdf-persistence --target-branch ci/release-pipeline
  --config-file release-please-config.json --manifest-file .release-please-manifest.json`.
  Record in the PR description:

| ID | Expected in the dry-run output | If not |
|---|---|---|
| DR-01 | latest release found: `v0.1.0` at `93fd447` | add `last-release-sha` (design Error matrix), re-run |
| DR-02 | proposed version `0.2.0` (breaking `4e33a70` + feats, PD-3) | check `bump-minor-pre-major`; stop if 1.0.0 |
| DR-03 | changed files: `pyproject.toml`, `uv.lock`, `.release-please-manifest.json`; no `CHANGELOG.md` | `uv.lock` missing → fallback of the Error matrix |
| DR-04 | notes have Added/Fixed/Changed and "BREAKING CHANGES" naming `require administer to delete a tenant`; no docs/test/ci lines | fix `changelog-sections` |
| DR-05 | tag name `v0.2.0` (no component) | fix `include-component-in-tag` |

## 2. Docs

- [ ] 2.1 `docs/modules/ROOT/pages/develop/index.adoc`: a section `[#release]` "Cutting a release":
  how a release PR appears; the bump rule before 1.0.0 (PD-3) and `Release-As: 1.0.0`; the
  CHANGELOG PR of PD-11 (rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`, add an empty
  `[Unreleased]`, update the two compare links); merge the release PR; what the workflow then does;
  once `build` is green, fast-forward `main` by hand with the one command of PD-1 (`git fetch
  origin --tags && git push origin "vX.Y.Z^{commit}:refs/heads/main"`, never `--force`; if refused,
  the Error matrix rows on `main`); if the release PR left `uv.lock` unchanged (the fallback of the
  Error matrix), open a `chore: uv lock` PR; a failed build is fixed forward (never re-tag); no
  PyPI yet, consumers install `develop` or pin `@vX.Y.Z`. Add the question "How is a release cut?" to `questions.adoc` pointing there.
  `CHANGELOG.md`: replace the "Release process" comment with one line pointing to that section;
  add under `[Unreleased]` → Changed: "Releases are proposed by release-please; `VERSION` removed,
  the version lives in `pyproject.toml`." In `develop/agents.adoc` "Merge and release", one
  sentence linking `#release`. Gates: `make check-docs`, `make check-diagrams` if a diagram is
  added (none planned).

## 3. Close and first release

- [ ] 3.1 `make check-all`; `openspec validate release-pipeline --strict`; PR into `develop`
  (Refs: release-pipeline DEC-1 DEC-2 DEC-4..DEC-9); merge on green CI. Then, by the pipeline
  (PD-9, PD-11), verify each row; the merge of the release PR is the developer's unless the epic's
  autonomy grant covers it:

| ID | Step | Expected |
|---|---|---|
| RL-01 | after the merge | release PR "chore(develop): release 0.2.0" open, as DR-01..05 |
| RL-02 | CHANGELOG PR merged | release PR refreshed, still 0.2.0 |
| RL-03 | release PR merged | tag `v0.2.0`; GitHub Release with the notes |
| RL-04 | `build` job | Release holds `rdf_persistence-0.2.0-py3-none-any.whl` and `rdf_persistence-0.2.0.tar.gz` |
| RL-05 | `ci.yaml` on the release commit; then the PD-1 push to `main`, by whoever merged the release PR | CI green; `git rev-parse origin/main` = `git rev-parse 'v0.2.0^{commit}'` |
| RL-06 | next `docs:`-only PR into `develop` | no release PR (spec scenario "only docs and chores") |

- [ ] 3.2 Archive the change (`/opsx:archive`).
