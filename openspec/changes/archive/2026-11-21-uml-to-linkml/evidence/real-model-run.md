# The converter on the consumer's real model, before stage 2 (D-23)

2026-11-20, `develop` at `593046a6` plus stage 1. Read-only (`file:…?mode=ro`); output in
`temp/`, never committed.

```
rp-uml2linkml <consumer>/docs/<model>.qea --package <root package> \
  --prefixes temp/<prefixes copy>.yaml --out temp/uml-real --root-name <root>
```

## Element types in the converted package

Classes 51 (23 «root», 1 «tenant root», 3 «loaded graph», 24 plain), boundaries 27, enumerations 6
(1 «workflow states»), notes 10, packages 11; connectors: associations 70, generalisations 25,
dependencies 7. Activity, Component, Interface, Decision, Abstraction and ControlFlow occur only in
two packages outside the converted one, and no connector links them to it: no rule needed.

## Run 1: the real file

- Exit 2: the prefixes file lacks `schema_base`, then `version` (consumer fix; a copy with both
  was used).
- Exit 1, 2 problems: one abstract class straddles two boundaries (`no_rule`).

## Run 2: a temp copy with that class taken off the diagrams

Exit 1, 16 problems:

| Count | Problem | Resolution (D-23) |
|---|---|---|
| 1 | «tenant root» class: no rule | R-18, stage 2 |
| 1 | its boundary: 0 roots | R-18, stage 2 (a «tenant root» counts) |
| 8 | `shared_slot_across_packages` | R-24, stage 2 |
| 1 | «workflow states» enumeration: no rule | R-30 (new), task 2.10 |
| 2 | `class_iri`: two IRIs share a local name (`identifier`, `template`) | consumer model fix |
| 3 | boundaries of one package hold no «root» | consumer model fix (or `--exclude-package`) |
| (run 1) | class straddles two boundaries | consumer model fix |

Rules added to #196 since its four comments: none.
