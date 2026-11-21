# Real-model run, stage 1 (task 1.4)

Counts and shapes only; no consumer, role or class names.

## Stage 1: roles (2026-11-21, base 436e616a)

Command shape, on a read-only copy of the probed model (the model was never edited):

```
rp-uml2linkml <copy>.qea --package <root package> --prefixes <prefixes>.yaml --out <out>/ \
  --root-name app --exclude-package <technical-mapping package> --exclude-package <workflows package> \
  --not-generated "loaded graph"
```

The workflows package is excluded because stage 2 is not delivered; the access package is converted.

| Measure | Value |
|---|---|
| Exit code | 1 (model problems; usage was accepted) |
| Problems | 1 |
| Problems by rule | `no_rule`: 1 (a boundary needs exactly one root, this one has 0) |
| Problems by a role rule (`role_run_state`, `role_definition`, `role_duplicate`) | 0 |
| Roles written | 0 (a failed run writes nothing, so no roles file exists) |
| Report lines by kind | none (the report is written only by a successful run) |
| Roles file loads with `load_role_definitions` | not checked: no file was written |

Read-only look at the model's tables, to say what the converter would have judged: the model draws
3 EA Objects, all 3 classified by a class named `RoleDefinition`, all 3 with a run state holding
`@VAR` blocks. None of them was refused by the role rules: the run produced no role problem.

The one problem is not about roles. The converted access package draws one aggregate boundary
with no root class inside it; the rule `no_rule` (boundary with 0 roots) fires on it. It did not
fire before because that package was excluded. The converter was not changed.

Next step for the model owner: put exactly one «root» (or «tenant root») in that boundary, or
remove the boundary; then rerun and fill the table above with the roles written, the `role`
report lines and the loader result.
