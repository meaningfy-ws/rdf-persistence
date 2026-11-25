# rp-generation Specification

## Purpose
How every model artefact is generated from the LinkML schemas by `rp-generate`: the checks that stop a bad schema, where each artefact goes, reproducible and fresh output, and the separation of technical models from domain models.

## Requirements

### Requirement: Generation fails on missing IRIs, labels or definitions

`rp-generate` SHALL fail, naming each offending element, when an element of the application schema
has no IRI (no declared `default_prefix` and no explicit `class_uri`/`slot_uri`), when a class, slot,
enum or permissible value has no `title` or no `description`, or when a permissible value has no
`meaning`.

#### Scenario: a slot without a description
- **WHEN** the toy schema declares a slot `isbn` without a `description`
- **THEN** `rp-generate` exits with an error naming `isbn`, and no output file changes

### Requirement: Generation fails on boundary violations

`rp-generate` SHALL fail when a class is reachable through a non-owned slot without being an
aggregate root, when a class is owned by nothing, or when a module annotated `module_kind: domain`
imports one annotated `technical` or `access`.

#### Scenario: a domain module imports the access module
- **WHEN** a domain module of the toy schema imports the toy access module
- **THEN** `rp-generate` fails and names both modules

### Requirement: Each artefact goes to its declared place

`rp-generate` SHALL write Python classes, shapes and the JSON-LD context to the backend path,
TypeScript types to the frontend path, and one Mermaid class diagram per schema module to the docs
path, as declared in the application's `[tool.rp-generate]` table; command-line flags SHALL override
the table. A failed run SHALL leave every previous output unchanged.

#### Scenario: placement from the table
- **WHEN** the toy application's table declares `typescript = "web/src/domain/generated"`
- **THEN** the TypeScript types are written there and nowhere else

### Requirement: Generated output is reproducible

Running `rp-generate` twice on the same schema with the same pinned `linkml` version SHALL produce
byte-identical output.

#### Scenario: regeneration in CI
- **WHEN** CI regenerates the toy library
- **THEN** the result equals the committed output

### Requirement: LinkML is the single source of every model artefact

Every model artefact SHALL be generated from the LinkML schema: domain classes, shapes, the JSON-LD
context and frames, TypeScript types, OpenAPI component schemas and diagrams.
No such artefact SHALL be written or edited by hand. A gap in a stock generator SHALL be closed by
a toolkit extension with its own test, and a rule the schema declares SHALL be enforced by the
generated classes as well as by the shapes.

#### Scenario: a hand-written domain class
- **WHEN** a module of `rdf_persistence.<theme>.domain` outside `generated/` defines a pydantic class
- **THEN** the model guard fails and names the class

#### Scenario: a consumer's class derived from the public base
- **GIVEN** a consumer module with `from rdf_persistence import RpModel` and `class Book(RpModel)` outside `generated/`
- **WHEN** the model guard runs on the consumer
- **THEN** it fails and names `Book`

#### Scenario: classes and shapes agree on a declared rule
- **WHEN** a `Grant` instance has both a role and an action, which `exactly_one_of` forbids
- **THEN** both the generated class and the generated shape refuse it

### Requirement: Stale or edited generated output is detected

`rp-generate --check` SHALL fail, naming the files, when an input of the last generation (the
schema closure, a template or an extension) has changed since, or when a generated file differs
from what was generated. The check SHALL run in `make check-quality`, at the start of every test
session and in CI. Its message SHALL end with a hint naming the command that regenerates: the
`regenerate-command` of each stale `[tool.rp-generate]` entry, or `rp-generate` for an entry that
sets none.

#### Scenario: a schema changed without regenerating
- **WHEN** a slot is added to the toy schema and `rp-generate` is not run
- **THEN** the test session stops before any test runs, naming the schema and the regenerating command

#### Scenario: a generated file edited by hand
- **WHEN** a line of a generated class file is changed by hand
- **THEN** `make check-quality` fails and names that file

#### Scenario: a model change is acknowledged
- **WHEN** a slot is added to the toy schema and the code is regenerated
- **THEN** the model-shape snapshot test fails until `make refresh-snapshot` is run

#### Scenario: an application that sets no command
- **GIVEN** a `[tool.rp-generate]` entry without `regenerate-command`
- **WHEN** its generated code is stale and the check runs through the CLI or the pytest plugin
- **THEN** the hint reads "run `rp-generate` to regenerate, then commit the result"

#### Scenario: an application that names its own command
- **GIVEN** a `[tool.rp-generate]` entry with `regenerate-command = "make generate-models"`
- **WHEN** its generated code is stale and the check runs through the CLI or the pytest plugin
- **THEN** the hint reads "run `make generate-models` to regenerate, then commit the result"

#### Scenario: a configuration error
- **GIVEN** a `[tool.rp-generate]` entry with an unknown key
- **WHEN** the pytest plugin runs
- **THEN** the session stops naming the key, and no regenerating command is suggested

### Requirement: A technical module may hold shapes that are never stored

The ownership rule SHALL NOT apply to classes of a module annotated `module_kind: technical`; they
SHALL be generated in Python and TypeScript. A class of a domain or access module that is neither a
root nor owned SHALL still be refused, except a class that descends from `Activity`, which is a
command or a record of the provenance graph and SHALL be exempt.

#### Scenario: an API shape in a technical module
- **GIVEN** a technical module with a class that is neither a root nor owned
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and generates the class in Python and TypeScript

#### Scenario: the same class in a domain module
- **GIVEN** a domain module with a class that is neither a root nor owned
- **WHEN** `rp-generate` runs
- **THEN** it fails with an ownership problem naming the class

#### Scenario: a command in a domain module
- **GIVEN** a domain module with `ShelveBooks`, a class that descends from `Activity` and is neither a root nor owned
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and reports no ownership problem for `ShelveBooks`

### Requirement: TypeScript targets get the service's types

When a target sets `typescript`, `rp-generate` SHALL also write the classes of the schemas the HTTP
API serves, among them the service's wire types, which are in
`rdf_persistence/model/technical/api/rp_api_entrypoints.yaml`, as one module `rp_service.ts`,
exported from `index.ts`. For such a target, the module name `rp_service`, the names of the served
schemas' modules and the names of their classes and enums SHALL be reserved, and every served schema
SHALL be an input of the target's manifest. A technical class that is not served SHALL add nothing
to `rp_service.ts`.

#### Scenario: a consumer with a web app
- **GIVEN** a consumer with `typescript` set in `[tool.rp-generate]`
- **WHEN** `rp-generate` runs
- **THEN** its TypeScript folder holds `AccountSummary`, `TenantSummary`, `Page`, `Problem` and
  `GrantSet`, all in `rp_service.ts`, and `tsc --strict` accepts them

#### Scenario: a consumer class named like a service type
- **GIVEN** a consumer with `typescript` set and a class named `Page`
- **WHEN** `rp-generate` runs
- **THEN** it fails with a problem naming `Page` as reserved by `rp_service.ts`

#### Scenario: the service schema changes
- **GIVEN** a consumer with `typescript` set and a fresh manifest
- **WHEN** the toolkit's `rp_api_entrypoints.yaml` or another served schema changes
- **THEN** the freshness check reports that schema as a stale input

### Requirement: The freshness check runs once per parallel session

Under `pytest-xdist`, the freshness plugin SHALL check the generated code once, in the controller,
before any worker starts, and SHALL NOT check again in the workers. A stale tree SHALL stop the
session once, with one message.

#### Scenario: a fresh tree on several workers
- **GIVEN** fresh generated code
- **WHEN** pytest runs with `-n 2`
- **THEN** the check runs in the controller only

#### Scenario: a stale tree on several workers
- **GIVEN** a stale generated target
- **WHEN** pytest runs with `-n 2`
- **THEN** the session stops before any test runs, with one message naming the target and the
  regenerating command

### Requirement: The REFERENCE problem names its fixes

The problem `rp-generate` reports SHALL, when a non-owned slot ranges over a class that is
neither an aggregate root nor a reference class, name the slot, its class and its range, and SHALL
name two fixes: annotating the slot `owned: true`, or making the range an aggregate root or pointing the slot at a root, `Principal` or `Activity`.

#### Scenario: a nested response class without owned
- **GIVEN** a technical module with class `Terms` whose slot `items` ranges over `Term`, not owned
- **WHEN** `rp-generate` runs
- **THEN** it fails with a REFERENCE problem whose text contains `owned: true` and names `Term`

#### Scenario: with owned
- **GIVEN** the same module with `annotations: {owned: true}` on `items`
- **WHEN** `rp-generate` runs
- **THEN** it reports no REFERENCE problem

### Requirement: A unique key across aggregates is declared with its scope

A `unique_keys` entry annotated `rp_unique_scope` SHALL be a key across aggregates; any other
`unique_keys` entry SHALL keep its in-aggregate meaning and its generated validators and shapes.
`rp-generate` SHALL fail, naming the class and the key, when a scoped key: has a scope other than
`tenant`; is declared on a class that is neither a tenant-database aggregate root nor an ancestor
of one; names a slot that is not a slot of every such root, or is multivalued, an identifier,
bookkeeping, or holds an owned part; or sets `consider_nulls_inequal: false` with a scope other
than `tenant`, the problem then naming `rp_unique_scope: tenant`. A scoped key with
`rp_unique_scope: tenant` and `consider_nulls_inequal: false` SHALL be accepted. It SHALL also fail
when a `unique_keys` entry on a tenant-database aggregate root has no `rp_unique_scope`. No
validator or shape SHALL be generated for a scoped key.

#### Scenario: a key on an owned part's slot
- **WHEN** the toy schema declares on `Book` a key `isbn_key` with `rp_unique_scope: tenant` over
  the slot `chapters`
- **THEN** `rp-generate` exits with an error naming `Book`, `isbn_key` and `chapters`, and no
  output file changes

#### Scenario: a key slot that is not a slot of the root
- **WHEN** the toy schema declares on `Book` a scoped key over a slot `binding` that `Book` lacks
- **THEN** `rp-generate` exits with an error naming `Book` and `binding`

#### Scenario: a root key without a scope
- **WHEN** the toy schema declares on `Book` a `unique_keys` entry without `rp_unique_scope`
- **THEN** `rp-generate` exits with an error naming `Book` and the key

#### Scenario: absent values counted at tenant scope
- **GIVEN** a scoped key with `rp_unique_scope: tenant` and `consider_nulls_inequal: false`
- **WHEN** `rp-generate` runs
- **THEN** it reports no problem for that key

#### Scenario: an unsupported scope
- **GIVEN** the option on a key whose scope is not `tenant`
- **WHEN** `rp-generate` runs
- **THEN** the hard check refuses it, naming the supported scope

#### Scenario: in-aggregate keys are unchanged
- **WHEN** the toolkit's own schemas are generated after this change
- **THEN** the validator and the shape of `Grant`'s key are as before

### Requirement: A stored class does not point at a consumer activity

A slot of a stored class SHALL NOT range over a consumer activity class that is not an aggregate
root; `rp-generate` SHALL refuse it with an `activity_direction` problem naming the class and the
slot. A slot MAY range over a toolkit activity class such as `Activity` or `Transition`, and an
activity class MAY point at stored classes.

#### Scenario: a book that points at a command
- **GIVEN** `Book`, a stored class, with a slot whose range is `ShelveBooks`
- **WHEN** `rp-generate` runs
- **THEN** it fails with an `activity_direction` problem naming `Book` and the slot

#### Scenario: a command that points at a book
- **GIVEN** `ShelveBooks` with the slot `used_resource` over `Book`
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and reports no `activity_direction` problem

### Requirement: A consumer does not redefine what the toolkit fills

A consumer class SHALL NOT redefine a toolkit-filled slot by `slot_usage`, `ifabsent` or an
attribute, SHALL NOT declare a slot whose expanded `slot_uri` is that of a toolkit-filled slot, and
SHALL NOT make a slot annotated `payload` required; `rp-generate` SHALL refuse each with a
`toolkit_filled` problem naming the class.

#### Scenario: a command that sets the start time
- **GIVEN** `ShelveBooks` with a `slot_usage` on `started_at_time`
- **WHEN** `rp-generate` runs
- **THEN** it fails with a `toolkit_filled` problem naming `ShelveBooks`

#### Scenario: a slot that aliases a toolkit-filled slot
- **GIVEN** `ShelveBooks` with a slot of its own whose `slot_uri` is that of `to_state`
- **WHEN** `rp-generate` runs
- **THEN** it fails with a `toolkit_filled` problem naming `ShelveBooks`

#### Scenario: a required payload slot
- **GIVEN** `ShelveBooks` with a `payload` slot that is required
- **WHEN** `rp-generate` runs
- **THEN** it fails with a `toolkit_filled` problem naming `ShelveBooks`

#### Scenario: the toy as it is
- **GIVEN** `ShelveBooks` with `used_resource` and its own `shelf_note`, and `Book`
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and reports no `toolkit_filled` problem

### Requirement: Technical models are generated apart from domain models

Each technical schema of the toolkit SHALL live under `rdf_persistence/model/technical/<theme>/`
as `rp_<theme>_<layer>.yaml` (settings, wire records, template variables, request and response
bodies), or as `rp_<theme>_settings.yaml` or `rp_<theme>_templates.yaml` for a non-served group
(D-15 (1)), or under `rdf_persistence/model/technical/testkit/` for the testkit records, annotated
`module_kind: technical`, and SHALL be generated into the `generated/` package of the lowest layer
that every user of its classes may import, in the lowest theme that uses them
(`<theme>/<layer>/generated/`, `<layer>` being `services`, `adapters` or `entrypoints`, and
`services` when both an adapter and an entrypoint use them; a `settings` or `templates` group into
`<theme>/<layer>/generated/settings/` or `<theme>/<layer>/generated/templates/`; a testkit record
into `testkit`),
apart from the domain models, which SHALL sit only in a `<theme>/domain/generated/` package. No
module of a domain layer, generated or hand-written, SHALL import a technical model; a technical
model MAY import a domain model. The domain schemas SHALL stay at their paths.

#### Scenario: a domain model imports a technical one
- **GIVEN** a copy of the toolkit where a generated domain module imports a technical model
- **WHEN** `make check-architecture` runs
- **THEN** it fails and names both modules

#### Scenario: a hand-written domain module imports a technical one
- **GIVEN** a copy of the toolkit where the IRI layout module of the `iris` theme's domain layer imports the service settings
- **WHEN** `make check-architecture` runs
- **THEN** it fails and names both modules

#### Scenario: the schemas a consumer imports
- **WHEN** a consumer schema imports `rdf_persistence/model/rp_core`
- **THEN** it resolves as before, and no technical schema can be imported that way

#### Scenario: a setting used by an adapter and by the service kit
- **GIVEN** the HTTP settings, read by the HTTP adapter base and composed into the toolkit settings the kit takes
- **WHEN** the toolkit is generated
- **THEN** their class is in `rdf_persistence.core.services.generated`, and no entrypoint imports an adapters package

#### Scenario: a wire record
- **GIVEN** the record of an identity provider's answer, used only by the identity adapter
- **WHEN** the toolkit is generated
- **THEN** its class is in `rdf_persistence.access.adapters.generated` and in no `domain` package

### Requirement: A target's kind is derived from its modules

`rp-generate` SHALL derive a target's kind from the modules it generates (the modules of its import
closure in its root schema's folder): `technical` when every one is annotated
`module_kind: technical`, `domain` when none is; a target whose modules are some technical and some
not SHALL fail, naming the target and its technical modules. A `[tool.rp-generate]` entry SHALL NOT declare `kind`;
an entry that does SHALL be refused, naming the key. Every target, the toolkit's and a consumer's,
SHALL generate into a package with a `generated` segment, whose segment before `generated` is
`domain` for a domain target, and `services`, `adapters` or `entrypoints` for a technical one; in the
toolkit's own run the segment before that SHALL be a theme of the library (the package is
`rdf_persistence.<theme>.<layer>.generated`). The packages `rdf_persistence.testkit` and
`rdf_persistence_generation`, and those inside them, SHALL be exempt. `rp-generate` SHALL fail,
naming the target, the package and the derived kind, otherwise, and write nothing; when the derived
kind is `domain` and the layer is a technical one, the message SHALL name the `module_kind: technical`
annotation as a fix.

#### Scenario: a domain module in a technical target
- **GIVEN** a toolkit target whose package ends in `.services.generated` and whose root schema generates a module annotated `module_kind: domain`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the target, its package and the derived kind `domain`, and no output file changes

#### Scenario: a target without a kind
- **GIVEN** the toy library's table, which declares no `kind` and generates into a `domain` package
- **WHEN** `rp-generate` runs
- **THEN** the kind `domain` is derived from its modules and it writes the same files as before

#### Scenario: a technical target pointed at a domain folder
- **GIVEN** a toolkit target of technical modules with a package ending in `.domain.generated`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails, naming the target and its package, and writes nothing

#### Scenario: an entry that still declares its kind
- **GIVEN** a consumer entry with `kind = "domain"`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the unknown key `kind`

#### Scenario: a technical target under no theme
- **GIVEN** a toolkit target of technical modules with `package = "rdf_persistence.services.generated"`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails naming the target and the package, which has no theme before its layer

#### Scenario: a domain target in an adapters folder
- **GIVEN** a toolkit target of domain modules with `package = "rdf_persistence.files.adapters.generated"`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails naming the target and the package

#### Scenario: a consumer's own layout
- **GIVEN** a consumer target of domain modules with `package = "app.generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** it fails naming the target and the package, which has no layer before `generated`

#### Scenario: a consumer's own themes
- **GIVEN** a consumer target of domain modules with `package = "app.catalogue.domain.generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** no folder problem is reported

#### Scenario: a target of both kinds
- **GIVEN** a target whose root schema generates one module annotated `module_kind: technical` and one not
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the target and the technical module

#### Scenario: a package with no layer at all
- **GIVEN** a consumer target with `package = "generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** it fails naming the target and the package, which has no layer before `generated`

#### Scenario: a consumer's settings without the annotation
- **GIVEN** a consumer target of settings modules not annotated `module_kind: technical`, with `package = "app.services.generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** it fails with the derived kind `domain`, and the message names the `module_kind: technical` annotation

### Requirement: A generated field can hold a toolkit type

The generator SHALL generate a LinkML type whose `repr` names a Python class, annotated
`python_import` with that class's module, as a field of that class, with its import. A SPARQL term field
SHALL accept only text that `term()` produced.

#### Scenario: a raw string in a SPARQL term field
- **GIVEN** a generated term model whose fields range over `sparql_term`
- **WHEN** it is built with a plain string
- **THEN** it is refused before any query text is made

### Requirement: A slot can default to an instance of its class

A slot annotated `default_instance: true` SHALL be generated so that, when no value is given, it
holds a new instance of its range class, a distinct instance for each object built. `rp-generate`
SHALL refuse the annotation, naming the slot and writing nothing, when the slot's range is not a
class, when the range class has a required slot without `ifabsent`, when the slot is multivalued,
or when the range class is declared after the class that holds the slot in the same module. A
multivalued slot whose `ifabsent` is `string(a, b, ...)` SHALL default to the list of those
values; any other `ifabsent` on a multivalued slot SHALL be refused, naming the slot.

#### Scenario: a group defaults to its own defaults
- **GIVEN** a class whose slot ranges over a class whose every slot has a default, annotated `default_instance`
- **WHEN** two objects of the class are built with no value for the slot
- **THEN** each holds an instance of the range class with its defaults, and the two instances are distinct

#### Scenario: a slot that cannot default to an instance
- **GIVEN** a slot annotated `default_instance` whose range is a type, or a class with a required slot without a default, or a class declared after its holder, or a multivalued slot
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the slot, and no output file changes

#### Scenario: a list default
- **GIVEN** a multivalued slot whose `ifabsent` is `string(RS256, ES256)`
- **WHEN** an object is built with no value for the slot
- **THEN** the slot holds the list `RS256`, `ES256`, a distinct list for each object

#### Scenario: a list default in another form
- **GIVEN** a multivalued slot whose `ifabsent` is `int(3)`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the slot

### Requirement: The generator is a sibling package installed with the library

The generator SHALL be the top-level package `rdf_persistence_generation`, shipped in the
`rdf-persistence` distribution beside `rdf_persistence`. The `rp-generate` command, the
`[tool.rp-generate]` table and its keys SHALL stay as they are. LinkML's generators SHALL be
installed only with the `generate` extra; without it, `rp-generate --check` SHALL still compare the
manifests, and `rp-generate` SHALL exit 2 naming the extra.

#### Scenario: generating with the extra
- **GIVEN** `rdf-persistence[generate]` installed and a `[tool.rp-generate]` entry
- **WHEN** `rp-generate` runs
- **THEN** the artefacts are written as before the move, byte for byte

#### Scenario: checking without the extra
- **GIVEN** `rdf-persistence` installed without the `generate` extra
- **WHEN** `rp-generate --check` runs on a fresh tree
- **THEN** it exits 0 after comparing the manifests

#### Scenario: generating without the extra
- **GIVEN** `rdf-persistence` installed without the `generate` extra
- **WHEN** `rp-generate` runs
- **THEN** it exits 2 and names `rdf-persistence[generate]`

### Requirement: The metamodel declares where its generated classes are imported from

Each metamodel module SHALL carry the annotation `python_package`, the package its classes are
generated into, and the root metamodel schema SHALL carry `public_package`, the package a
consumer's generated code imports metamodel classes from. The generator SHALL read both from the
metamodel. On the toolkit's own run, a module without `python_package`, or whose `python_package`
differs from the `python_package` of the root schema of the target that generates it, SHALL fail the
hard check, naming the module, the root and both packages. A module beside the root that names
another package is generated by another target; the toolkit's run checks it against the packages of
the toolkit's targets (a module of another target is imported, not generated again).

#### Scenario: a consumer's generated class
- **GIVEN** a consumer schema that imports `rp_core`
- **WHEN** it is generated
- **THEN** its classes import the metamodel classes from the `public_package`

#### Scenario: a module moved to another package
- **GIVEN** `rp_core.yaml` annotated with another `python_package` and the toolkit entry changed to match
- **WHEN** the toolkit's other targets are generated
- **THEN** they import `rp_core`'s classes from that package

#### Scenario: an annotation that disagrees
- **GIVEN** the `python_package` of a root schema (`rp.yaml`) differs from the `package` of the toolkit entry that generates it
- **WHEN** the toolkit's `rp-generate` runs
- **THEN** it fails naming the root and both packages, and writes nothing

#### Scenario: a module beside the root that names another package
- **GIVEN** a module beside the root of a target, whose `python_package` is the package of another toolkit target
- **WHEN** the toolkit's `rp-generate` runs
- **THEN** the target imports its classes and the check passes; were the package no toolkit target's, it would fail with `<module> names python_package <package>, which no toolkit target generates`

### Requirement: The generator has its own test pyramid

The generator's tests SHALL live in `tests/generator/{unit,feature,integration,e2e}`, apart from
the library's, each tier stamped by its folder. The feature tests SHALL generate the toy library;
the integration tests SHALL check freshly generated shapes with pySHACL, the context and frames
with PyLD, and the TypeScript with `tsc --strict`; the end-to-end test SHALL serve a freshly
generated toy library through the service kit on Fuseki.

#### Scenario: freshly generated code is served
- **GIVEN** the toy library generated into a new package in a temporary folder
- **WHEN** it is served through the service kit on Fuseki
- **THEN** a librarian creates, reads, replaces and deletes a book over the API, a reader is
  refused the write, and an outsider gets 404

#### Scenario: fresh shapes judge the conformance cases
- **GIVEN** the toy library freshly generated
- **WHEN** pySHACL validates each conformance case of the toy's classes against the fresh shapes
- **THEN** every valid case conforms, and every invalid case does not conform and its report names
  the constraint of the case's kind, except a `closed` case, which the reader of the fresh
  documents refuses before the shapes see it

### Requirement: A module of another target is imported, not generated again

When a schema imports a module that declares `python_package`, and that package is not the
`python_package` of the target's root schema, `rp-generate` SHALL import that module's classes from
that package in the generated code, SHALL NOT generate them again, and SHALL record the imported
module's file as an input of the target, whether or not the module sits beside the root schema. In
the toolkit's run, such a module SHALL name the package of one of the toolkit's targets, or the hard
check SHALL fail with `PYTHON_PACKAGE_MISMATCH`, `<module> names python_package <package>, which no
toolkit target generates`. A module beside the root schema without
`python_package`, or beside a root that declares none, SHALL be generated into the target; a
consumer's import of the metamodel SHALL still go through the metamodel's public package.

#### Scenario: one theme's technical schema uses another's
- **GIVEN** a target whose schema imports a module declaring `python_package: pkg.access.services.generated`
- **WHEN** `rp-generate` runs
- **THEN** the generated code imports that module's classes from `pkg.access.services.generated` and defines none of them

#### Scenario: a module beside the root of another target
- **GIVEN** the toolkit target rooted at `rdf_persistence/model/rp_tenancy.yaml`, which imports `rp_core.yaml` beside it, declaring `python_package: rdf_persistence.core.domain.generated`
- **WHEN** `rp-generate` runs
- **THEN** its classes import `rp_core`'s from `rdf_persistence.core.domain.generated`, and the target writes no file for `rp_core`

#### Scenario: a package no target generates
- **GIVEN** a toolkit module beside the root whose `python_package` is the package of none of the toolkit's targets
- **WHEN** the toolkit's `rp-generate` runs
- **THEN** the hard check fails with `PYTHON_PACKAGE_MISMATCH`, naming the module and the package: `<module> names python_package <package>, which no toolkit target generates`

#### Scenario: a consumer's module beside its root
- **GIVEN** a consumer schema with no `python_package`, importing a module beside it
- **WHEN** `rp-generate` runs
- **THEN** that module is generated into the consumer's target, as before

### Requirement: Generated consumer code imports the toolkit from its public package

The Python classes `rp-generate` writes for an application SHALL import every toolkit name,
`RpModel` included, from `rdf_persistence` and from no deeper module.

#### Scenario: the toy library
- **WHEN** the toy library is generated
- **THEN** each generated module imports `RpModel` from `rdf_persistence`, and `testkit.assert_public_imports` finds no deep import in it

### Requirement: Each domain module is generated in its theme

Each module of the toolkit's domain model SHALL be generated into the `domain/generated/` package of
its theme: `rp_core` and `rp_annotations` into `rdf_persistence.core.domain.generated`, `rp_access`
and `rp_tenancy` into `rdf_persistence.access.domain.generated`, `rp_provenance` into `provenance`,
`rp_files` into `files`, and `rp_collections`, `rp_discussion` and `rp_workflow` into
`collaboration`, each importing the classes of the modules it uses from their packages. One combined
`shapes.ttl`, `context.jsonld` and set of frames, built from all the domain modules, SHALL be
generated into `rdf_persistence.core.domain.generated`, with the model's migrations lock. The
toolkit's run SHALL write no root module that imports every theme.

#### Scenario: the access concepts
- **WHEN** the toolkit is generated
- **THEN** `Grant`, `Policy`, `RoleDefinition` and `TenantAccess` are defined in `rdf_persistence.access.domain.generated`, and no module of `rdf_persistence.core` defines or imports them

#### Scenario: the combined shapes
- **WHEN** the toolkit is generated
- **THEN** `rdf_persistence/core/domain/generated/` holds one `shapes.ttl`, one `context.jsonld` and the frames, built from every domain module, with the same set of frames as before the split, the migrations lock sits beside the metamodel, and the committed files equal a regeneration

### Requirement: LinkML may be generated from a UML class model

The LinkML a project generates from MAY itself be written by `rp-uml2linkml` from an Enterprise
Architect model instead of by hand. `rp-generate` SHALL treat that LinkML as any other schema: the
same checks, the same targets and the same freshness rules, with no step that knows where the
LinkML came from. The UML model is then the source the modellers edit, and the LinkML is
regenerated whole from it.

#### Scenario: a converted schema is generated like a hand-written one
- **GIVEN** a project whose LinkML was written by `rp-uml2linkml`
- **WHEN** `rp-generate` runs
- **THEN** it applies its lint, boundary, hard and rules steps and writes its targets exactly as for
  a hand-written schema

### Requirement: The identifier slot is never a property

The identifier slot of a class (`identifier: true`) SHALL be the node's IRI and never a statement:
no generated shape SHALL hold a property shape for it, and no slot SHALL be resolved from a
predicate to it. A slot of the application on the identifier's `slot_uri` SHALL keep its own range.

#### Scenario: a business identifier on the identifier's property
- **GIVEN** a class with the toolkit's `id` and a slot `identifier` on `dcterms:identifier`, range `string`
- **WHEN** a body gives `identifier` the value `tpl-1`
- **THEN** the shapes accept the literal, and the stored object reads back with its IRI and `tpl-1`

#### Scenario: the node of an identified class
- **WHEN** the shapes are generated
- **THEN** each identified class's shape requires an IRI node and has no property shape that asks `dcterms:identifier` for an IRI

### Requirement: A slot name resolves to the application's slot over an internal toolkit slot

Where a slot of the application has the name of a toolkit slot under another `slot_uri`, and no
toolkit class carries that toolkit slot, every reader of the schema (the runtime, the shapes, the
JSON-LD context, the component schemas) SHALL resolve the name to the application's slot, whatever
the order of the imports. The toolkit's own metamodel SHALL keep its slot.

#### Scenario: a module's own version
- **GIVEN** a module that defines `version` on `dcat:version` and imports the toolkit
- **WHEN** the root imports the module before the toolkit, or after it
- **THEN** the view and the merged schema both resolve `version` to `dcat:version`, and a value given to it is stored and read back

### Requirement: An application slot does not take the name of a carried toolkit slot

`rp-generate` SHALL refuse a slot of the application that takes the name of a toolkit slot that a
toolkit class carries, under another `slot_uri` (rule `toolkit_slot_name`). The problem SHALL name
both slots, their IRIs and the carrying toolkit classes.

#### Scenario: an application slot named graph
- **GIVEN** an application module that defines `graph` on `lib:graph`, while the toolkit's registry entry carries `graph`
- **WHEN** the developer regenerates
- **THEN** generation fails with `[toolkit_slot_name] graph:` naming both definitions

### Requirement: A value module generates never-stored domain values

A module annotated `module_kind: value` SHALL be generated into the domain layer (a package ending
in `domain.generated[.<group>]`). Its classes SHALL be exempt from the ownership, owned-class and
aggregate-root rules, and SHALL NOT be aggregate roots or tenant roots. A value module SHALL import
only domain, value and toolkit modules. A stored class SHALL NOT hold a class of a value module; it
MAY use an enum of one. A module of another target that imports a value module declaring
`python_package` SHALL import its classes from that package and not generate them again.

#### Scenario: a value module in the domain layer
- **GIVEN** a `module_kind: value` module with an enum and two classes that are neither roots nor owned
- **WHEN** `rp-generate` runs on a target whose package is `library.domain.generated.values`
- **THEN** the boundary and hard checks report no problem and the Python classes are generated

#### Scenario: a technical module reuses the value classes
- **GIVEN** a technical module that imports the value module
- **WHEN** both targets are generated
- **THEN** the technical module's Python imports the value classes from the value package, so both hold the same class

#### Scenario: a value module imports a technical module
- **WHEN** the boundary check runs
- **THEN** it refuses the value module with a `module_kind` problem and a hint to move the class

#### Scenario: a value class declared as a root
- **GIVEN** a value class that mixes in `AggregateRoot`
- **WHEN** the boundary check runs
- **THEN** it refuses the class: a value is never stored

### Requirement: A slot over an abstract aggregate root is a reference

A slot whose range has `AggregateRoot` among its ancestors and is not owned SHALL be generated as a
reference whether its range is abstract or concrete: `str` (or `list[str]`) in Python, `string` in
TypeScript, `sh:nodeKind sh:IRI` in the shapes.

#### Scenario: a loan lends an item
- **GIVEN** an abstract `Item` mixing in `AggregateRoot`, concrete roots below it, and a root `Loan` with `lends: {range: Item, required: true}`
- **WHEN** `rp-generate` runs
- **THEN** `Loan.lends` is `str` in Python and `string` in TypeScript, and an instance naming a book by its IRI validates and round-trips

### Requirement: Modules of one target that import each other generate Python that loads

When modules that one target generates import each other, directly or through others,
`rp-generate` SHALL write Python that imports in any order: every module of the cycle, the root
module and the package import without error, whichever is imported first, and their classes
validate nested data typed by a class of another module of the cycle. A class of another module of
the same cycle that a module names only in annotations SHALL be imported for the type checker
only, and the package's `__init__.py` SHALL complete those classes once every module of the cycle
is loaded. A module in no cycle, and the `__init__.py` of a target with no cycle, SHALL be written
exactly as they were before this requirement. When the modules of a cycle need each other's
classes while they load (as an `is_a` parent or mixin, a `default_instance` default or a member of
a `union_of`), `rp-generate` SHALL fail at its `python` step, naming the modules and the classes,
and SHALL leave the target's generated files as they were.

#### Scenario: two domain modules that refer to each other
- **GIVEN** a target whose root imports `app_books` and `app_shelves`, each importing the other,
  `Book` referring to a `Shelf` and `Shelf` owning a part declared in `app_books`
- **WHEN** `rp-generate` runs, then `rp-generate --check`
- **THEN** both exit 0, and importing `app_shelves` first, or `app_books` first, gives classes that
  build a `Shelf` with its part from nested data

#### Scenario: a target with no cycle is written as before
- **GIVEN** the toolkit's own targets and the test library, none of whose modules import each other
- **WHEN** they are generated
- **THEN** every generated file, `__init__.py` included, is byte-identical to the one written
  before this requirement

#### Scenario: a cycle that Python cannot load
- **GIVEN** `app_a` and `app_b` importing each other, a class of `app_a` with its `is_a` parent in
  `app_b` and a class of `app_b` with its `is_a` parent in `app_a`
- **WHEN** `rp-generate` runs
- **THEN** it exits 1 with a `python` problem naming `app_a`, `app_b` and the two parents, and
  the target's generated files are left as they were

### Requirement: Two slots do not share one IRI

`rp-generate` SHALL refuse a target whose import closure, toolkit included, has two slots or class
attributes with different names on one expanded IRI, one of them declared in the target's own
modules (rule `slot_iri`). A slot or attribute with `identifier: true` SHALL be left out of the
comparison. The problem SHALL name every slot on that IRI with its module, and the IRI.

#### Scenario: an application slot on the toolkit's membership predicate
- **GIVEN** an application module that defines `parts` on `dcterms:hasPart`, while the toolkit's `has_part` is on `dcterms:hasPart`
- **WHEN** the developer regenerates
- **THEN** generation fails with `[slot_iri]` naming `parts`, `has_part` and `http://purl.org/dc/terms/hasPart`, and nothing is written

#### Scenario: a business identifier beside the identifier slot
- **GIVEN** a class with the toolkit's `id` (`identifier: true`) and a slot `identifier`, both on `dcterms:identifier`
- **WHEN** the developer regenerates
- **THEN** generation succeeds as before

#### Scenario: a default IRI and an attribute on another slot's IRI
- **GIVEN** a slot with no `slot_uri` whose default IRI (the module's default prefix and its name) is another slot's `slot_uri`, or a class attribute on another slot's `slot_uri`
- **WHEN** the developer regenerates
- **THEN** generation fails with `[slot_iri]` naming both
