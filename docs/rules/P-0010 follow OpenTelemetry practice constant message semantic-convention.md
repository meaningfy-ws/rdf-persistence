---
kind: rule
id: P-0010
type: constraint
strength: hard
status: active
scope:
  - activity:coding
when: adding or changing logging or tracing
do: "follow OpenTelemetry practice: constant message, semantic-convention attribute names, exc_info for errors, spans through opentelemetry-api only"
because: logs must correlate with traces and be queryable
source: 2026-11-16 'the logging must be aligned to best logging practices in OpenTelemetry'
added: 2026-11-17
approved: 2026-11-17
last_confirmed: 2026-11-17
private: false
---
