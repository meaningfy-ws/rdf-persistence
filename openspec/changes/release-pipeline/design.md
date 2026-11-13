> Derives from: EPIC `release-pipeline` (proposal.md). Implements DEC-1, DEC-2, DEC-4 to DEC-9.
> Type: Implementation.

## Context

`.github/workflows/release.yaml` (projected from the Meaningfy template) runs
`googleapis/release-please-action@v4` with `release-type: python` on every push to `develop`, then
builds with `pipx run build` and publishes to TestPyPI and PyPI. It has never released: with no
`target-branch` it looks for releases on `main`, the repository's default branch, and with no
config or manifest it finds "No version for path ." (every run, last on #77, succeeds in ~45 s
doing nothing).

Facts checked on 2026-11-12:

- `v0.1.0` is tag and GitHub Release on `93fd447`, the merge of PR #22 (`release/0.1.0` into
  `develop`). `main` was then moved to that commit by hand and has not moved since; `develop` is 187
  commits ahead (31 `feat`, 20 `fix`, 2 `perf`, one breaking: `4e33a70 feat(router)!: require
  administer to delete a tenant`; the rest `docs`, `test`, `ci`, `refactor`, `build`, `style` and
  merge commits).
- The version is written in four places: `VERSION`, `pyproject.toml` (`version = "0.1.0"`, with a
  comment that `VERSION` is the source), `rdf_persistence/__init__.py` (`__version__ = "0.1.0"`)
  and `uv.lock` (the editable root package entry). Nothing reads `VERSION`.
- The build backend is `uv_build>=0.10,<0.11`. It does **not** support a dynamic version: a
  `pyproject.toml` with `dynamic = ["version"]` fails `uv build` with "missing field `version`"
  (tried in `temp/`, uv 0.13.5). So the version must be a literal in `pyproject.toml`.
- Generated code (`rdf_persistence/domain/generated/`) is committed and kept fresh by the
  freshness check, so `uv build` needs no generator (`make build` runs `generate` first; the
  release job does not need to).
- `ci.yaml` runs on PRs into `develop` and on push to `develop` (both with `paths-ignore` for
  `docs/**` and `*.md`). `main` and `develop` are unprotected; no ruleset; no GitHub environment
  exists. Workflow token permission is `write` and Actions may create PRs.
- A PR or tag created with `GITHUB_TOKEN` triggers no other workflow, so `ci.yaml` will not run on
  the release PR itself. Its merge into `develop` is a push by a person and touches
  `pyproject.toml`, `uv.lock` and the manifest, so `ci.yaml` does run on the release commit.
- `GITHUB_TOKEN` cannot be given the `workflows` permission, and GitHub refuses a push by it that
  creates or updates a file under `.github/workflows/`. Moving `main` from `93fd447` to `develop`
  brings changes to `ci.yaml` and `docs.yaml` (`git diff --stat 93fd447 origin/develop --
  .github/workflows`), so a fast-forward of `main` by the workflow would be refused.
- CI installs with `uv sync --all-extras` (Makefile), without `--locked`, so a stale root version in
  `uv.lock` is rewritten locally and never fails CI.

## Goals / Non-Goals

**Goals:** the three requirements of `specs/rp-release/spec.md`: releases proposed from
Conventional Commits and merged by a human; one version file and a release that matches the tag;
`main` holds the last release. The pending 0.2.0 is cut by the pipeline's first run.

**Non-goals:** the EPIC's No-gos (PyPI, release and hotfix branches, pre-releases, signing).

## Decisions

Every PD is the **leader's choice (2026-11-12), the developer may overrule** it (inputs/seed.md:
"accept recommendations, and continue"), unless it cites the developer.

- **PD-1** (DEC-9; seed Q-1): release-please runs on push to `develop` with `target-branch:
  develop`; the release PR targets `develop` and its merge commit carries the tag. After a release,
  the person who merged the release PR fast-forwards `main` to the tag **by hand**, with the one
  command in the how-to (`git fetch origin --tags && git push origin
  "vX.Y.Z^{commit}:refs/heads/main"`, no `--force`; git refuses a non-fast-forward). This keeps
  `main` = last release (its GitFlow role, and what v0.1.0 did by hand) with one PR per release,
  instead of a `develop`→`main` PR, a release PR on `main` and a back-merge. No `release/X.Y.Z`
  branch: this library needs no stabilisation period before 1.0.0. Why by hand, not a workflow job
  (gate 1, PD-12): `GITHUB_TOKEN` cannot push commits that change `.github/workflows/*` (Context),
  and every release that follows a CI change would hit it. Automating it needs a GitHub App or a
  fine-grained token with `workflows: write` stored as a secret, which only the developer can
  create; one command per release does not justify that today (YAGNI). Upgrade path: the developer
  adds the secret, and a `main` job (`needs: [release-please, build]`, checkout with that token,
  the same push) replaces the manual step.
- **PD-2** (DEC-5; seed Q-2): `pyproject.toml` is the only version file (uv_build cannot read a
  dynamic version; see Context). `VERSION` is deleted. `rdf_persistence/__init__.py` sets
  `__version__ = importlib.metadata.version("rdf-persistence")`, so it cannot drift. release-please's
  `python` strategy bumps `pyproject.toml`; one `extra-files` entry (TOML, JSONPath) bumps the root
  package in `uv.lock`.
- **PD-3** (DEC-1; seed Q-3): `bump-minor-pre-major: true`, `bump-patch-for-minor-pre-major: false`.
  Before 1.0.0: breaking → MINOR, `feat` → MINOR, `fix`/`perf` → PATCH. 1.0.0 is declared by the
  developer with a `Release-As: 1.0.0` commit footer, never by the bump rule.
- **PD-4** (DEC-4): `skip-changelog: true`. The repository already curates `CHANGELOG.md` by hand
  under `[Unreleased]` in each PR (richer than commit subjects; it names breaking changes and
  migrations). release-please writes only the release notes (release PR body and GitHub Release
  body) with `changelog-sections` mapped to Keep a Changelog names: `feat`→Added, `fix`→Fixed,
  `perf`→Changed, `revert`→Changed; `docs`, `test`, `ci`, `build`, `style`, `refactor`, `chore`
  hidden. Breaking changes get their own section from release-please. Why not let release-please
  write the file: it would insert a second, commit-shaped entry next to the curated one on every
  release, and a human would delete it each time.
- **PD-5** (DEC-8; seed Q-6, the developer 2026-11-06): the `testpypi` and `pypi` jobs and the
  `id-token` permissions are **removed**, not disabled behind a flag: dead jobs rot, and a disabled
  job still needs the `release` environment to make sense. The template and git history hold them;
  PyPI is its own later change (DEC-3's method).
- **PD-6** (seed Q-4): the `build` job runs on a release only: `actions/checkout@v4`,
  `astral-sh/setup-uv@v6` (the version `.github/actions/setup` uses), `uv build`, then two checks
  before upload: the wheel `dist/rdf_persistence-${VERSION}-py3-none-any.whl` exists, and
  `uv run --no-project --isolated --with <wheel> python -c "import rdf_persistence;
  print(rdf_persistence.__version__)"` prints `${VERSION}` (no `generate` extra installed); then
  `gh release upload "$TAG" dist/*`. It does not re-run tests: the PRs merged into `develop`
  passed CI, the release PR changes only `pyproject.toml`, `uv.lock` and the manifest, and
  `ci.yaml` runs on the release commit anyway (push to `develop`, Context).
- **PD-7** (seed Q-5): approval is the review of the release PR (four-eyes on the version and the
  notes). No `release` environment or required reviewers: nothing is published outside GitHub.
- **PD-8** (seed Q-7, Q-8): no attestations, signing or SBOM; no pre-releases. Both need PyPI or a
  consumer asking first.
- **PD-9**: the pending 0.2.0 is cut by the pipeline's first run, not by hand: merging this
  change's PR into `develop` makes release-please propose 0.2.0 (31 `feat` and one breaking change
  since v0.1.0, PD-3), which is the pipeline's acceptance test. The lead merges the release PR only
  under the epic's autonomy grant; otherwise the developer merges it.
- **PD-10**: `include-component-in-tag: false` so the tag is `vX.Y.Z`, the form `v0.1.0` already
  has; the manifest starts at `{".": "0.1.0"}`. The workflow has `concurrency: {group: release,
  cancel-in-progress: false}` so two quick pushes to `develop` never run release-please in parallel.
- **PD-11** (attack): the CHANGELOG is moved under the new version in an ordinary PR into `develop`
  (`docs(changelog): release X.Y.Z`), not by a commit on release-please's branch: release-please
  rebuilds its branch on every push to `develop` and would drop a human commit there. That PR is
  merged, release-please refreshes the release PR, and the release PR is merged right after.
- **PD-12** (gate 1, 2026-11-12): an independent clarity-gate review scored this PLAN 8/10; its
  four findings are folded in: `main` is fast-forwarded by hand, not by the workflow (PD-1, Error
  matrix "push refused"); the `uv.lock` fallback is a follow-up `chore: uv lock` PR after the
  release, not part of the CHANGELOG PR (Error matrix); Context corrected (`ci.yaml` also runs on
  push to `develop`) and RISK-1 shrunk; the `main` job and its `needs` are gone from task 1.2.

## Algorithm / approach

`release-please-config.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "include-component-in-tag": false,
  "bump-minor-pre-major": true,
  "bump-patch-for-minor-pre-major": false,
  "skip-changelog": true,
  "changelog-sections": [
    {"type": "feat", "section": "Added"},
    {"type": "fix", "section": "Fixed"},
    {"type": "perf", "section": "Changed"},
    {"type": "revert", "section": "Changed"},
    {"type": "docs", "section": "Docs", "hidden": true},
    {"type": "test", "section": "Tests", "hidden": true},
    {"type": "ci", "section": "CI", "hidden": true},
    {"type": "build", "section": "Build", "hidden": true},
    {"type": "style", "section": "Style", "hidden": true},
    {"type": "refactor", "section": "Refactor", "hidden": true},
    {"type": "chore", "section": "Chores", "hidden": true}
  ],
  "packages": {
    ".": {
      "package-name": "rdf-persistence",
      "extra-files": [
        {"type": "toml", "path": "uv.lock",
         "jsonpath": "$.package[?(@.name.value=='rdf-persistence')].version"}
      ]
    }
  }
}
```

`release.yaml` (shape):

```yaml
on: {push: {branches: [develop]}}
concurrency: {group: release, cancel-in-progress: false}
permissions: {contents: write, pull-requests: write}
jobs:
  release-please:
    outputs: {released: ..release_created, tag: ..tag_name, version: ..version}
    steps: [release-please-action@v4 with config-file, manifest-file, target-branch: develop]
  build:            # if released == 'true'
    steps: checkout, setup-uv@v6, uv build, check wheel name + import version, gh release upload
# no `main` job: `main` is fast-forwarded by hand (PD-1)
```

`release-please` outputs `released`, `tag` and `version`; `build` reads them.

Worked example, the first run after this change merges:

| Step | Who | Result |
|---|---|---|
| This change's PR merges into `develop` | lead | release-please reads the manifest (0.1.0), finds Release `v0.1.0` at `93fd447`, reads 187 commits, opens "chore(develop): release 0.2.0" changing `pyproject.toml`, `uv.lock`, `.release-please-manifest.json` |
| `docs(changelog): release 0.2.0` PR: `[Unreleased]` → `[0.2.0] - <date>`, new empty `[Unreleased]`, compare links | lead | merged; release PR refreshed, still 0.2.0 |
| Release PR reviewed and merged | developer, or lead under autonomy | tag `v0.2.0` on the merge commit; GitHub Release with the notes |
| `build` job | workflow | wheel + sdist checked, attached to `v0.2.0` |
| `ci.yaml` on the release commit | workflow | green (push to `develop`) |
| `git push origin "v0.2.0^{commit}:refs/heads/main"` | whoever merged the release PR, after `build` is green | `main` fast-forwarded from `93fd447` to the release commit |
| Next `fix:` PR merges | — | release PR "release 0.2.1" opens |

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Keep `VERSION` "for scripts" | Delete it (PD-2) | Nothing reads it; two files drift (DEC-5) |
| `dynamic = ["version"]` in `pyproject.toml` | A literal version bumped by release-please | uv_build refuses it (Context) |
| Hand-edit the version or push the tag | Let the release PR do it | One bumper (DEC-5); a hand tag confuses release-please's history |
| Commit on `release-please--branches--develop` | A normal PR into `develop` (PD-11) | release-please force-rebuilds its branch |
| Keep the PyPI jobs behind `if: false` | Remove them (PD-5) | Dead code; YAGNI; the developer deferred PyPI |
| `git push --force` to `main` | Fast-forward only | A non-ff means someone moved `main`; stop and look |
| Run `make build` in the release job | `uv build` (PD-6) | `make build` runs the generators, which need the `generate` extra; the code is committed and fresh |
| Squash-merge feature PRs with a non-conventional title | Conventional PR title, or a merge commit | release-please reads the squash commit's subject |

## Error matrix

| Situation | Result |
|---|---|
| Only `docs`/`test`/`ci`/`chore`/`refactor`/`style`/`build` commits and merge commits since the last tag | release-please logs no user-facing commits; no release PR; job green |
| Merge commits ("Merge pull request #N …") | not Conventional; ignored; the commits they bring in are read one by one |
| A commit message that is not Conventional | ignored for the bump and the notes (lost from the notes, not an error) |
| `feat!` / `BREAKING CHANGE:` before 1.0.0 | MINOR bump (PD-3), listed under "⚠ BREAKING CHANGES" |
| release-please cannot find `v0.1.0` (proposes 0.1.0 again or reads all history) | caught by the dry run of task 1.3 before merging; fix: `"last-release-sha": "93fd4475dc0a3c946011d254074a5db02e500708"` in the config, removed by the first PR after 0.2.0 |
| `extra-files` JSONPath does not match `uv.lock` | caught by the dry run (`uv.lock` absent from the changed files); fallback: drop the entry; after each release, a follow-up PR `chore: uv lock` into `develop` refreshes the root version (release-please has no lockfile updater, and a `uv lock` in the CHANGELOG PR would run before the bump). Until it merges the lock is stale, which is only noise: CI runs `uv sync` without `--locked` |
| A PR merges into `develop` while the release PR is open | release PR refreshed (version may rise); nothing tagged |
| Wheel version ≠ tag, or import fails | `build` fails; nothing attached; `main` is not moved (the how-to moves it only after a green `build`); the tag and Release exist: fix forward with a PATCH release, never re-tag |
| `main` is not an ancestor of the release commit | the manual push is refused (non-fast-forward); `main` unchanged; look at who moved `main` before doing anything else, never `--force` |
| Push to `main` refused (missing `workflows` permission, or a branch protection or ruleset added later) | `main` unchanged; nothing else is affected (tag, Release, wheel stand). Push with a credential that may update workflow files and is allowed by the protection (the developer's own), or ask the developer to relax the rule; never through `GITHUB_TOKEN` |
| `gh release upload` fails (network) | job fails; re-run the job (upload is idempotent with `--clobber`) |
| Two pushes to `develop` in quick succession | the second run waits (concurrency group) |
| Release PR merged with squash or with a merge commit | either: the tag goes on the resulting commit on `develop` |

## Risks / Trade-offs

- **RISK-1** — the release PR gets no CI run before merge (`GITHUB_TOKEN` PRs trigger no
  workflows) (certain; low impact: it changes only version metadata, and `ci.yaml` runs on the
  merged release commit, Context). Accepted; the `build` job checks the wheel after merge.
- **RISK-6** — someone forgets to fast-forward `main` after a release (medium; low: consumers
  install `develop` or pin a tag; `main` only lags). The how-to puts the command right after "merge
  the release PR"; the next release's push catches up, since a fast-forward skips any number of
  releases.
- **RISK-2** — no hotfix path: a fix for a released version ships with whatever unreleased work is
  on `develop` (medium likelihood once consumers pin; low impact before 1.0.0, as consumers install
  `develop`). Accepted; GitFlow `hotfix/` branches come with PyPI or 1.0.0.
- **RISK-3** — the curated `[Unreleased]` and the generated notes disagree (medium; low). The
  CHANGELOG is the durable record (DEC-4); the reviewer of the release PR compares them.
- **RISK-4** — the `uv.lock` JSONPath recipe (`@.name.value`) depends on release-please's TOML
  parser (low; low). Covered by the dry run and its fallback (Error matrix).
- **RISK-5** — someone keeps hand-editing `CHANGELOG.md`'s compare links wrong (low; low). The
  how-to in `develop/index.adoc` lists the exact edit.
- **Assumption** — release-please v4 finds the latest release from the manifest version and the
  GitHub Release `v0.1.0`; verified by the dry run of task 1.3 before anything merges.

## Open Questions

None blocking; each was decided by default above. For the developer to confirm or overrule: PD-1
(cut from `develop`, `main` fast-forwarded by hand), PD-4 (release-please does not write the
CHANGELOG), PD-5 (PyPI jobs removed), PD-9 (0.2.0 cut by the pipeline's first run).

Setup only the developer can do, if wanted (not needed by this PLAN): to automate the `main`
fast-forward, create a GitHub App (or a fine-grained token) with `contents: write` and `workflows:
write` on this repository, store it as a repository secret, and ask for the `main` job of PD-1's
upgrade path.
