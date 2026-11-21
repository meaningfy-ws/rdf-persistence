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

## Stage 2: workflows (task 2.4, 2026-11-21, base ff3d3035)

Both runs on the same read-only copy, nothing excluded about workflows. Counts and rule codes only.

Run A, as D-8 expected (the access package converted):

```
rp-uml2linkml <copy>.qea --package <root package> --prefixes <prefixes>.yaml --out <out>/ \
  --root-name app --exclude-package <technical-mapping package> --not-generated "loaded graph"
```

Run B, the access package left out to exercise the workflows part:

```
rp-uml2linkml <copy>.qea --package <root package> --prefixes <prefixes>.yaml --out <out>/ \
  --root-name app --exclude-package <technical-mapping package> --exclude-package <access package> \
  --not-generated "loaded graph"
```

| Measure | Run A | Run B |
|---|---|---|
| Exit code | 1 | 1 |
| Time | 0.5 s | 0.5 s |
| Problems | 1 | 8 |
| Problems by rule | `no_rule`: 1 (a boundary needs exactly one root, this one has 0: the same as stage 1) | `workflow_transition`: 8 (each: a role the transition names is not drawn as a role definition, DEC-5) |
| Workflow rules other than `workflow_transition` (`workflow_node`, `workflow_initial`, `workflow_definition`, `workflow_duplicate`, `workflow_class`), `no_rule` on a state or flow | 0 | 0 |
| Workflow files written | 0 | 0 |
| Roles written | 0 | 0 |
| Report lines by kind | none (a failed run writes no report) | none |

What the model draws, read from its tables (read-only): 1 Statechart diagram of 6 nodes (1 Initial,
5 States), 9 StateFlows (1 untagged out of the Initial node, 8 tagged with both `roles` and
`comment_required`), 1 class carrying a `workflow` tag. No substate, no state operation, no flow with
a name, stereotype, `PDATA` text or trigger row (the rows RISK-5 asked to list): none of the
`no_rule` refusals applies.

Reading of the results:

* Run A stops at the model's own boundary problem before any role or workflow is written, so the
  workflows are not yet exercised with the access package converted (D-8, RISK-3). Once the model
  owner fixes that boundary the run decides the roles and workflows together.
* Run B shows the workflow side: the diagram's structure (one Initial flow, the five states, the
  eight transitions' other tags, the class's `workflow` tag, the name) raises no problem. The only
  failures are the 8 transitions whose roles are drawn in the excluded access package: exactly
  RISK-3's predicted consequence of converting the workflows without the roles.
* The diagram's name has no prefix in the probe (RISK-2), so a successful run would add one
  `derived-iri` line; not observable here, as a failed run writes no report.
* The converter was not changed. Nothing it does looks wrong; the strict role check works as
  designed (DEC-5).

Still to fill from a later run, once the model's boundary is fixed: workflows and roles written,
report lines by kind, and the loaders' result on the written files.
