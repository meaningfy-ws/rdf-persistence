# EA connector columns (task 1.0, RISK-9, D-4, D-5)

2026-11-28, lead.

## Documentation

Sparx Systems' user guide (sparxsystems.com/enterprise_architect_user_guide/17.0/, including the
automation-interface pages) refused automated fetches (HTTP 403), so no sentence of the official
documentation is quoted here. The column semantics below rest on observation only.

## Observed in an EA-saved model (read-only, column values only)

One EA-saved `.qea` available locally holds no connector of type `Aggregation`. Its composite
associations (`Connector_Type = Association`, drawn whole → part) carry `SourceIsAggregate = 2`,
`DestIsAggregate = 0` and an empty `SubType`: the value 2 sits on the end of the whole, the end
that shows the diamond.

## What the reader assumes (PD-1, D-5)

For an `Aggregation` connector, the end column holding 2 is the whole and the end column holding 1
is a shared aggregation; `SubType` is not read. The drawing direction never matters, since the
reader takes whichever end is marked.

## Probe (task 1.13, RISK-9), 2026-11-28

At the developer's request (acceptance, 2026-11-28), the lead read every EA-saved `.qea` on the
developer's machine, read-only, column values only:

| Model | Connector rows read |
|---|---|
| an architecture model (32 `Aggregation` connectors) | `Aggregation`, `SubType` `Weak`, `SourceIsAggregate=0`, `DestIsAggregate=1`, `Direction` `Source -> Destination` (29); the same with an empty `SubType` (3) |
| four further models | composite associations, `SourceIsAggregate=2` or `1`, `DestIsAggregate=0` |
| four further models | no aggregation |

Findings:

- EA records an `Aggregation` connector the way it records an association's ends: the aggregation
  kind sits in the end column of the whole (the diamond end). These were drawn part → whole, so it
  is `DestIsAggregate`. `SubType` names the kind (`Weak` for shared) and is sometimes empty.
- The converter's reader (`read_qea`), run on that model, read all 27 Aggregation connectors of its
  converted package as shared aggregations and refused each with "a shared aggregation; draw a
  composition (strong) or a plain association". The end-column rule of PD-1 and D-5 holds on real
  EA rows, and the drawing direction does not decide the whole.
- Not observed: a composite `Aggregation` (value 2), since none of the local models draws one. The
  value 2 is EA's composite mark on the association rows above, in the same columns. The developer
  accepted this residual with the probe.

RISK-9 is closed. PD-1 and `QeaBuilder.aggregation` need no correction.
