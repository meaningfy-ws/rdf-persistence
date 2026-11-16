# Clarity gate: aggregate-events PLAN (design.md + tasks.md)

- run 1, 2026-11-15, 8.8/10, fail (12 gaps: class lookup by IRI, tenant states, `Offer`,
  test parameters, TC-31 venv, relay concurrency, decoder left to the builder, resume filtering,
  feature coverage, log levels, naming, document type)
- run 2, 2026-11-15, 9.3/10, pass (all 12 gaps closed; read only for the gaps)

Before run 2 the PLAN was also revised after a fresh adversarial review (11 findings): store-side
`NOW()` order (PD-1, PD-5), per-database rounds and the failed mark (PD-3), the decoder (PD-16),
the receive probe and `TenantBehind` (PD-10), resume by `rp:relayedAt` (PD-12), the overtaken
commit published (PD-2, spec delta), the deployment check (PD-15), RISK-7 to RISK-9.

No accepted gap; no DEC added.
