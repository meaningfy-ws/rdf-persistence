# Acceptance: technical-models

- **Date:** 2026-11-17
- **Verdict:** accepted by the developer, without a demo.
- **Demo:** skipped at the developer's instruction ("skip the demo, I accept it"). The change is
  LARGE and moves boundaries and constructors, so a demo was due; the developer waived it.
- **What stands in for it:** the full gates of each stage (`make check-all`,
  `make test-containers`), green CI on PRs #144, #145, #146, #150 and PR 4, the BDD feature
  `tests/feature/technical_models.feature` (one scenario per delta scenario), the full review of
  the whole change at stage 4 (L1, L2, L3, L4+L5), and the cold read of `howto/settings.adoc` and
  `howto/adopt.adoc`.
- **Not validated by a person:** the settings how-to as a consumer upgrading would follow it; the
  first consumer (MWBv2) meets it at its next upgrade.
