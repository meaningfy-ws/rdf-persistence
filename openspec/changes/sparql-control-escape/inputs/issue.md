# #270 SPARQL literal escaping breaks on a control character followed by hex digits

`tests/unit/core/test_sparql.py::test_any_string_literal_round_trips` fails on the Hypothesis example `text='\x1f0000'`:

```
ValueError: Invalid unicode code point: 001f0000
  rdflib/plugins/sparql/parser.py, expandUnicodeEscapes
```

rdflib's SPARQL parser reads the escape written for `\x1f` together with the four digits after it as one code point, so a string literal holding a control character followed by hex digits does not parse back. The defect is in the literal escaping of `rdf_persistence/core` (it must write an escape rdflib cannot extend, e.g. the 8-digit `\U` form). It reproduces wherever `.hypothesis/` holds the example.

Found while delivering `test-debt-paydown` (`openspec/changes/archive/2026-11-21-test-debt-paydown/handover.md`, item 1).

