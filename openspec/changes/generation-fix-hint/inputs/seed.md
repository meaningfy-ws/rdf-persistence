<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: the freshness fix hint names the application's command

## Seed text

GitHub issue #25, copied in `issue.md`. `FIX_HINT` in `rdf_persistence/generation/manifest.py:21`
says "run `make generate` …"; a consumer (MWB2) names its target `make generate-models`, and the
adoption guide tells applications to name theirs `make generate` only to match the message.

## What was read

- `rdf_persistence/generation/manifest.py` (`FIX_HINT`, `freshness_problems`),
  `rdf_persistence/generation/cli.py` (`_freshness`), `rdf_persistence/testkit/freshness.py`
  (`pytest_sessionstart`), `rdf_persistence/generation/config.py` (`_toml_entries`,
  `TOML_SCHEMA_KEY`), `rdf_persistence/generation/model/rp_generation.yaml` (`GenerationTarget`).
- `pyproject.toml`: this repository has four `[[tool.rp-generate]]` rows.
- Tests naming the hint: `tests/unit/generation/test_freshness.py` (lines 105, 116, 131),
  `tests/unit/generation/test_freshness_plugin.py:44`.
- `openspec/specs/rp-generation/spec.md` ("Stale or edited generated output is detected").
- `docs/modules/ROOT/pages/howto/adopt.adoc` step 4.

## Questions and answers (developer, 2026-11-08)

1. **Which fix?** Options: the hint names `rp-generate` (recommended by the leader: no new
   setting), or that default plus a `regenerate-command` setting. **Answer: the default plus the
   `regenerate-command` setting.**

## Leader's choices while planning (recorded, not asked)

- `[tool.rp-generate]` may be an array of tables, so the setting is a key of each entry; the hint
  names the distinct commands of the stale entries (design PD-2).
