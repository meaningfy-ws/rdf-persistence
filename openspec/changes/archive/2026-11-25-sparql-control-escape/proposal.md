<!-- Parents: GitHub issue #270; openspec/specs/rp-aggregate-store/spec.md
     ("SPARQL is never built by concatenating input"). Seed: inputs/issue.md. -->

# EPIC: A control character followed by hex digits survives SPARQL escaping

**Golden-thread parent:** GitHub issue #270 and the `rp-aggregate-store` requirement "SPARQL is
never built by concatenating input".

## Appetite

**TINY.** One concern: the escape `term` writes for a control character.

## Why

`term` writes a control character as a 4-digit `\uXXXX` escape. rdflib's SPARQL parser expands
`\u` with 4 or 8 hex digits, greedily, before it parses, so `"\x1f" + "0000"` goes out as
`\u001f0000` and is read as the code point `001f0000`: the parse fails ("Invalid unicode code
point"). Where the eight digits happen to form a valid code point (`"\x01" + "0000"` reads as
U+10000) the parse succeeds and the store keeps a different string than the caller gave. Found by
Hypothesis on `test_any_string_literal_round_trips`.

## Solution outline

Write every control character as the 8-digit `\UXXXXXXXX` escape, which is already the form `term`
uses after an escaped backslash. No reading extends an escape that has eight digits, in rdflib or in
any SPARQL 1.1 parser, so the digits after it stay text.

## Key decisions

- **DEC-1**: Control characters go out as `\U` with 8 upper-case hex digits. Source: issue #270.
  Rejected: escaping the following hex digit as well (two rules for one concern); a raw control
  character (SPARQL allows most, but `\x00` and some stores do not).

## Rabbit-holes

- Fixing rdflib's greedy expansion upstream. The toolkit writes an escape every reading agrees on.

## No-gos

- No change to which characters are escaped, nor to IRIs, language tags or blank nodes.

---

## What Changes

- `rdf_persistence/core/domain/sparql.py` `_string`: the control-character escape is
  `\UXXXXXXXX` instead of `\uXXXX`.
- `tests/unit/core/test_sparql.py`: the issue's example in `HOSTILE` and a property over every
  control character followed by 1 to 9 hex digits.
- `tests/integration/store/test_session.py`: the hostile round trip through Fuseki takes the
  issue's example too.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-aggregate-store`: the escaping requirement now states that a literal is read back exactly as
  given, whatever characters it holds (what #270 broke), and gains the scenario of a control
  character followed by hex digits.

## Impact

- The SPARQL text the toolkit sends changes for literals holding control characters; what the store
  holds is unchanged, except that the corrupted or failing cases now round-trip. No API change.

## Reconciliation

| Item | State | PR |
|---|---|---|
| DEC-1, tasks 1.1 and 1.2 | delivered as shaped, with review fixes RF-1 to RF-4 | #388 |
