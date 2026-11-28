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

## Open (RISK-9)

Not yet observed: how EA writes an `Aggregation` connector drawn part → whole and whole → part, and
a shared one. The developer draws these in a scratch model before any release (task 1.12, `@manual`
scenario "An EA-drawn composition reads the same either way"); the lead then records the columns
here and corrects PD-1 and `QeaBuilder.aggregation` if they differ.
