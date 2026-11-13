# Acceptance — tenant-dump-restore

- **Demo:** offered on 2026-11-13 (appetite MEDIUM, may be skipped). **Skipped by the developer**,
  2026-11-13. Reason: IT-01 runs the use case (dump a tenant with an aggregate, loaded graphs and a
  blob; restore it for another principal; the copy answers like the original) on the real Fuseki and
  Garage containers on every `make test-containers`.
- **Decision confirmed at acceptance:** restore checks structure only (graph names, root, blob keys,
  sizes), not each aggregate's shapes (PD-13); the developer kept it on 2026-11-13.
