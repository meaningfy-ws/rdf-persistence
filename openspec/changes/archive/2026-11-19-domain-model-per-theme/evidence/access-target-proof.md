# RISK-3 proof: the `access` target end to end (task 1.2)

RISK-3: a cross-target edge the generator does not handle (an enum or mixin of `rp_core` used by
`rp_access`). Proved in a scratch copy of the worktree after PD-1 to PD-5; nothing of it is carried
into the worktree (the annotations and the entry are task 2.1).

## What was run

In the scratch copy (the repo without `.git` and `.venv`):

1. `rdf_persistence/model/rp_access.yaml` and `rp_tenancy.yaml`: `python_package:
   rdf_persistence.access.domain.generated` (was `…core.domain.generated`).
2. `pyproject.toml`: a second `[[tool.rp-generate]]` entry after `rp.yaml`: `schema =
   "rdf_persistence/model/rp_tenancy.yaml"`, `package = "rdf_persistence.access.domain.generated"`,
   `openapi = false`, no `migrations`.
3. `rp-generate --project pyproject.toml`, through the worktree's environment with the copy first on
   `sys.path` (`uv run --no-sync python -c "…cli.main(['--project','pyproject.toml'])"`, since the
   `rp-generate` script would load the worktree's code).
4. A probe that imports the generated modules and checks their classes. It stubs the package
   `rdf_persistence` in `sys.modules`: the eager imports of `rdf_persistence/__init__.py` still name
   the old module paths, which task 2.1 rewrites.

## What was seen

- `rp-generate: generated 21 target(s), no problems`: the hard check passed on both targets, with no
  `migrations` on the access target although `TenantAccess` is a root (E-6, PD-4).
- `rdf_persistence/access/domain/generated/` holds `rp_access.py`, `rp_tenancy.py` and the target's
  own `shapes.ttl`, `context.jsonld`, `TenantAccess.frame.jsonld`, `__init__.py`.
- `core/domain/generated/` no longer holds `rp_access.py`, `rp_tenancy.py` nor `rp.py` (the root
  has no classes of its own, PD-5).
- `rp_access.py` imports `Principal` from `rdf_persistence.core.domain.generated.rp_core`;
  `rp_tenancy.py` imports `Described` (`rp_annotations`) and `AggregateRoot` (`rp_core`) from core and
  `Grant`, `Policy`, `Prohibition` from `.rp_access`. Every enum and mixin of `rp_core` that
  `rp_access` uses resolves; no module of core imports the access package, so there is no cycle.
- The probe imported all seven remaining core modules and both access modules. `TenantAccess` is a
  subclass of `rp_core.AggregateRoot`, `Grant` lives in `rdf_persistence.access.domain.generated.rp_access`,
  `TenantState` has `ACTIVE`, `DELETING`, and `TenantAccess.model_fields` holds `database_name`,
  `description`, `grants`, `id`, `label`, `prohibitions`, `state`, `store_name`.
- RISK-2 side: the combined `core/domain/generated/shapes.ttl`, `context.jsonld`,
  `TenantAccess.frame.jsonld` and `migrations/schema.lock.json` are byte-identical to the worktree's
  (`cmp`), since they stay on `own_schemas` (PD-1).

## Result

No cross-target edge is left unhandled for the `access` target: RISK-3 is retired for it.

## Not covered

- `import rdf_persistence` (task 2.1 rewrites its eager imports and the 104 deep imports).
- The `files`, `provenance` and `collaboration` targets (the same mechanism; task 2.1 generates them).
