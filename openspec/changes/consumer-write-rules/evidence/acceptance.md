# Acceptance: consumer-write-rules

- **Demo:** skipped by the developer, 2026-11-28 ("Continue, and skip demo"). The appetite is
  MEDIUM, where the demo is offered and may be skipped (`epic-delivery`,
  `verification-validation.md`).
- **Evidence instead:** the four signed feature scenarios run in `tests/feature/consumer_write_rules.feature`
  (a rule refuses with the consumer's problem and names the holder; a holder in another tenant is
  not found; a holder the writer may not read is not named; a rule under unit test with the
  testkit's reader), the gate reports of PR #434 and PR #447, and the full review (D-21).
- **Not accepted as delivered, by the developer's own decision:** the OpenAPI document listing the
  registered problem classes (task 1.4, D-5), back to shaping.
