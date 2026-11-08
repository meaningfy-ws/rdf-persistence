> Derives from: EPIC `generation-fix-hint` (proposal.md), GitHub issue #25.

## 1. The setting

- [x] 1.1 Add the `regenerate_command` slot to `GenerationTarget` in
  `rdf_persistence/generation/model/rp_generation.yaml` (design PD-1) and run `make generate`.
  Test first in the config tests: `regenerate-command` is read into the model, a non-string is a
  `ConfigError` naming the TOML key; then extend the key mapping in
  `rdf_persistence/generation/config.py`. Gates: `make test`, `make check-all`.

## 2. The hint

- [x] 2.1 Test first (`tests/unit/generation/test_freshness.py`,
  `tests/unit/generation/test_freshness_plugin.py`): the two new scenarios of
  `specs/rp-generation/spec.md` through the CLI and the plugin, two stale entries with two
  commands, two projects with one hint (PD-5), and a configuration error with no hint (PD-6).
  Then add `stale_targets` and `fix_hint`, delete `FIX_HINT` (PD-2, PD-3) in `manifest.py`, and use
  them in `cli.py` and `testkit/freshness.py`; update the existing assertions that name `make generate`.
  Set `regenerate-command = "make generate"` on this repository's entries (PD-4). Gates:
  `make test`, `make check-all`.

## 3. Docs

- [x] 3.1 `docs/modules/ROOT/pages/howto/adopt.adoc` step 4: the target may have any name; show
  `regenerate-command`. Also `architecture/generation.adoc:541` ("Add `make generate` calling
  `rp-generate`") and `questions.adoc:51`: neither may require the target's name. The pages that
  describe this repository's own `make generate` (`develop/index.adoc`) stay. Gate: `make check-docs`.

## Roadmap

- [x] 1.1 · [x] 2.1 · [x] 3.1

## Verification

`make check-all` and `make check-docs` green; `openspec validate generation-fix-hint --strict`
passes; issue #25 closed by the PR.
