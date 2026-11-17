# Docs owed: otel-observability

The EPIC changed user-facing behaviour (log attributes and messages, spans, a new constructor
argument), so a docs stage runs. The how-to `howto/observability.adoc` was written in task 2.6,
cold-read and revised in stage 2. What remained (design.md D-13), done in the close PR:

| Page | Owed | Source |
|---|---|---|
| `howto/observability.adoc` | `rp.sweep.system_created` described as the code means it | L2-W4 |
| `model/technical/telemetry/rp_telemetry.yaml` | the same slot's description (regenerated) | L2-W4 |
| `howto/event-driven.adoc` | `RedisEventBus`'s arguments after technical-models stage 3, and `middlewares=` | L2-W5 |
| `howto/observability.adoc` | `rp.step` in the store-span table | L2-S1 |
| `howto/observability.adoc` | §6: a span records an exception's type only (D-10) | checker F2 |

No architecture page changes: no ADR is contradicted by what was built.
