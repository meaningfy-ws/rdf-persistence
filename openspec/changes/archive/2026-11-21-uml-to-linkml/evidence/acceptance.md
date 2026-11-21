# Acceptance demo: uml-to-linkml (task 2.8)

2026-11-21, branch `feat/uml-to-linkml-stage2` at `48b95801` (PR #228), and again at `3c1fcb40`
after the review's fix pass, with the same results. The converter ran on the
first consumer's real Enterprise Architect model, read-only (the file's SHA-256 is the same before
and after: `ef711f5780c51399…`). Output in `temp/`, never committed. Every run used:

```
rp-uml2linkml <consumer model>.qea --package <root package> --prefixes <prefixes copy>.yaml \
  --root-name <root> --not-generated "loaded graph" --not-generated "workflow states" --out temp/…
```

| Run | Input | Exit | Problems by rule | Report by kind |
|---|---|---|---|---|
| 1 | the real file | 1 | `no_rule` 2 (one class straddles two boundaries) | — |
| 2 | temp copy, that class taken off the diagrams | 1 | `class_iri` 4 (two IRIs share a name: `end_date`, `identifier`, `start_date`, `template`), `no_rule` 3 (three boundaries of one package hold no «root»), `shared_slot_across_packages` 3 (the same names as the clashes) | — |
| 3 | run 2 with `--exclude-package` on that package | 1 | `class_iri` 1 (`template`) | — |
| 4 | run 3 on a copy with that one attribute renamed | 0 | — | `no-note` 41, `toolkit-slot-kept` 14, `not-generated` 6, `toolkit-filled` 2, `merged-cycle` 1 |

Run 4 wrote 7 modules and the root schema. `rp-generate --check` on them stops at lint: 22 slots
without a description, the `no-note` lines of the report (RISK-2).

Against the run before stage 2 (`real-model-run.md`, 18 problems): the «tenant root» and its
boundary now convert (R-18), the shared slots across packages fall from 8 to the 3 tied to name
clashes (R-24), and the «workflow states» enumeration is left out (R-30). What remains is the
consumer's model to fix, as D-23 sorted it: the straddling class, the four name clashes, the
package with no root, and the missing notes.

## Verdict

**Accepted, with follow-ups** (the developer, 2026-11-21). The follow-up is the review's floor
(`design.md` D-29), opened as #229 ("uml-to-linkml hardening"). The developer also validated the
delivery decisions D-1..D-29 (R-0007). The consumer's model fixes listed above are the consumer's.
