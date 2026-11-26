# Changelog

All notable changes to **RDF Persistence** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **The testkit carries the test queue, the selection-data tools and the changed-tests planner**
  (`test-control-testkit`). `rdf_persistence.testkit.run_queue` (the machine-wide queue and the
  worker count), `rdf_persistence.testkit.selection_data` (the seed, swap and check of the
  selection data) and `rdf_persistence.testkit.changed_tests` (the tests a change reaches, from a
  project's own `Classifier` and `ChangedTestsLayout`) replace the repository's own
  `tests/queue.py`, `tests/testmon_data.py` and the generic part of `tests/changed.py`; a project
  runs them by module name or from its own file and needs only `pytest-testmon` and `pytest-xdist`.
  The testkit's model gains `SelectionDataOutcome` and the changed-tests records.

### ⚠ BREAKING
- **A module another target writes as TypeScript is no longer copied into the importing target's
  folder** (`consumer-friction`, #371). The importing target's TypeScript files import its types
  from the owner's folder by a relative path, and its `index.ts` no longer lists the module. Before,
  the module was copied, so its types existed twice. To fix it, import the types from the owner's
  folder. A module whose owner does not set `typescript` is copied as before.

## [0.15.0] - 2026-11-25

### Added
- **The testkit releases library caches between tests** (`agent-test-control`,
  `rdf_persistence.testkit.memory_plugin`). After every test it clears the caches of
  linkml-runtime's `SchemaView`, FastAPI's dependency models and `typing`, which otherwise keep
  every service a test built alive; at each module boundary it also collects garbage and returns
  freed memory to the system. A project that builds services with the toolkit in its tests enables
  it with one line in its root `conftest.py`:
  `pytest_plugins = ["rdf_persistence.testkit.memory_plugin"]`. `TEST_RELEASE=off` turns it off.

### Fixed
- **A string literal holding a control character followed by hex digits round-trips through SPARQL**
  (`sparql-control-escape`, #270). `term()` wrote a control character as `\uXXXX`, and rdflib reads
  `\u` with four or eight hex digits, so `"\x1f0000"` failed to parse as the code point `001f0000`,
  and `"\x010000"` was silently stored as U+10000. Control characters now go out as `\UXXXXXXXX`,
  which no reading extends. The SPARQL text sent for such literals changes; what the store holds is
  what the caller gave.

## [0.14.0] - 2026-11-25

### ⚠ BREAKING
- **`rp-generate` refuses two differently named slots or attributes on one expanded IRI**
  (`slot-uri-clash`, rule `slot_iri`). A model that declares, for example, `parts` on
  `dcterms:hasPart` while the toolkit's `has_part` already sits there generated before; now the
  hard check fails, exit 1, nothing is written, and the problem names every slot on the IRI with
  its module. Slots and attributes with `identifier: true` are exempt. To fix it, reuse the existing
  slot, or give yours its own `slot_uri`. See the hard checks in "Model to code: the generation workflow".
- **The UML converter writes one module per package and never merges a cycle**
  (`generator-module-cycles`). The merge of packages that refer to each other, and the failure of
  merged packages with different kinds, both described in `[0.8.1]`, are removed, and so is the
  `merged-cycle` report line. Before, packages that referred to each other were written as one
  module named after the first in path order, so their classes lived in that module; now each
  package is its own module (`app_catalogue`, `app_shelves`) and the modules import each other.
  A class of a later package moves to its package's module, and a slot shared between packages may
  take another home module. Imports through the root module are unchanged. Regenerate converted
  schemas and update imports of the moved classes that name their module. Packages of different
  kinds that import each other are now converted and refused by `rp-generate`'s boundary check;
  classes that inherit both ways between two packages are refused by `rp-generate`: move them into
  one package. See "Packages and modules" in "UML conventions".

### Added
- **Ask which roles the caller holds** (`grant-roles` stage 2, #310, #367). `Collaboration.roles_held(iri)`
  returns the role names the caller holds on an aggregate: its role grants in scope plus the token
  roles defined at system level, by the same rule as a comment's audience and the transitions. It
  needs read access and refuses as `thread` does; the discussion module is not required. Every
  aggregate and tenant read now sends `Held-Roles` beside `Allowed-Actions`: the names sorted and
  comma separated, empty when none is held. The OpenAPI document declares both headers. See "Ask
  which roles the caller holds" in the access user manual.

### Changed
- **A role name holds no comma** (#367). A roles file that names a role with a comma (`a,b`) is
  refused when it loads, and so is a migration whose `grant_roles.rename` targets such a name, so
  `Held-Roles` always reads back as the names held.

### Fixed
- **The start-up report names each undefined role once** (`grant-roles`, #375). The stale-grants
  warning repeated a `level:role` pair for every grant naming it; it now lists each pair once, in
  the grants' order.
- **The UML converter refuses sibling packages of one name with different kinds**
  (`generator-module-cycles`). Two such packages share a module; without the removed merge the last
  kind won silently. The converter again reports the module and both kinds.

## [0.13.0] - 2026-11-25

### Added
- **A listing filters through references** (`reference-filters`). `<reference>.<slot>=<value>` and
  `<reference>.<slot>~=<text>` read the slot in the aggregate the reference points to, up to three
  references deep (`author.name~=le`). Each hop is a listable reference to an aggregate root in the
  same database; an aggregate the caller may not read does not match; `absent=` and `sort=` take no
  path. A path that breaks these answers 400 `bad-query`. A reference collection's membership rule
  takes no path either (422 `invalid-body`). Every aggregate listing in the OpenAPI
  document now carries a description of the syntax. See "Filters through references" in the HTTP API
  reference.
- **Held writes in the testkit** (`consumer-test-gaps` stage 1, #323, #319). `FakeStore.hold(operation,
  until, timeout=5.0)` is an async context manager: the first `until` calls of `operation` inside
  it wait for each other, then run one by one in arrival order, so a test can make two writers
  meet at one version without patching the store. Hold `update` inside `kit.relay.paused()`. The
  testing page now shows how to aim a fault at the request with `kit.relay.paused()` (#319). See
  "Test the service".
- **Referrers say where to read them** (`consumer-test-gaps` stage 2, #320). `Referrer` gains the
  optional `referrer_rp_path` and `referrer_id`, set together in the `in-use` problem and in
  `Collaboration.referrers` when the referrer's class is a served root and its IRI is an aggregate
  IRI of the policy, so `GET {tenant_segment}/{t}/{referrer_rp_path}/{referrer_id}` reads it.
  `Iris.aggregate_id_of(iri)` gives the id an aggregate IRI ends in; `install_problem_handlers` and
  `in_use_problem` take an optional `locate`, which `install_service` wires. Neither field is set
  for an unserved class, a foreign IRI or an unfiltered refusal, and the other members are unchanged.

### Fixed
- **The UML converter keeps a redrawn role's own cardinality** (`consumer-test-gaps` stage 3,
  #332). When the usages of a slot differ on a cardinality, each class's `slot_usage` now writes
  its own `minimum_cardinality` (0 included) and finite `maximum_cardinality`; before, a subclass
  that redrew a `2..*` role as `1`, or a `0..5` role as `0..1`, inherited the ancestor's bound.
  Regenerate your model: slots whose usages differ gain explicit cardinalities. An unbounded role
  under a bounded `is_a` ancestor's (`0..5` redrawn `0..*`; or `0..1` redrawn `0..*` when another
  class bounds the same role at another maximum) now fails conversion with `cardinality_unbounded`
  (R-31); bound the role or unbind the ancestor's.

## [0.12.0] - 2026-11-24

### Added
- **Delete rules** (`aggregate-guards` stage 2, #309, #346). `install_service` and `ServiceKit`
  take `delete_validators`: a mapping from a class of the schema to rules called as
  `(old, principal, reader)`, checked at start-up as `aggregate_validators` are. They run on every
  transaction remove of a root of that class or a derived one, cascades included, before anything
  is removed; with none registered, a remove reads nothing more. A rule refuses by raising
  `Refused`, a new `Conflict` exported from `rdf_persistence` with `DeleteValidator`. The rule's
  reader answers only for what the caller may read, on the generic delete and on
  `remove_with_files` (which takes the caller's `may_read`). See "Control access".
- **The `refused` problem** (#309). A rule's refusal answers 409 with the problem type `refused`,
  whose `detail` is the rule's message; a version or key conflict still sends no text. A stale
  `If-Match` is the version conflict, not the refusal. The `ProblemSlug` enum, the OpenAPI
  components and the served TypeScript gain `refused`.
- **Rename and drop roles in stored grants** (`grant-roles` stage 1, #307, #310, #345). A
  migration file takes `grant_roles` with `rename: {old: new}` and `drop: [names]`; on the system
  database it renames or drops the role of every stored grant (a rename that would duplicate a
  grant the assignee already holds removes the duplicate), then rotates the version tokens. Other
  databases and `migrate_dataset` get no grant operations. A drop of a renamed name, a chain, a
  self-rename, a name renamed twice or an empty name is refused when the file loads. See "A model
  round renames or drops a role" in the migration how-to.
- **Stale grants reported at start-up** (#307, #345). After `migrate_shared`, the service warns
  for each tenant whose grants name an undefined `(level, role)` and for each tenant no grant
  administers; a store failure or an undecodable record is logged at ERROR. Start-up never stops.
  `AccessRules` gains `undefined_roles` and `administered`.

### Changed
- **A lone `dct:hasPart` role to the collection's own class now fixes `member_class`**
  (`converter-hardening`, #260). A reference collection whose only `dct:hasPart` role to a
  converted class points at itself becomes a collection of collections: its own class is its
  member class. Beside a role to another class, or when another collection in its class
  hierarchy fixes a member class, the self-role stays nesting, as before. A model that drew a
  lone self-role to mean nesting now gets a `member_class` and refuses `nests` data after
  regeneration: draw the member class instead. See "A reference collection's member class" in
  the UML conventions.
- **A roles file that gives a key twice in one entry now stops the service at start**
  (`converter-hardening`, #258). `load_role_definitions` reads through the same reader as the
  workflow files, so a repeated key is an `InvalidRoleDefinition` naming it; before, the last
  value silently won.

### Fixed
- **Schema modules that import each other now generate Python that loads** (#208). `rp-generate`
  used to refuse them: the `[0.8.1]` entry on the Python import check describes the run that
  failed on two modules that import each other. Now the names a module only annotates are imported
  under `if TYPE_CHECKING:`, and the package's `__init__.py` binds them and rebuilds the classes, so
  either module can be imported first. A target with no such modules is written as before. A cycle
  that needs a class of the other module while it loads (a parent class, a default instance, a
  union alias) is still refused, naming the modules and classes: put those classes in one module, or
  break the cycle. Import the package, not a module by path, and a class from its own module or the
  root module.
- **Role definitions are read as UTF-8 whatever the locale** (#258); a byte that is not UTF-8
  is an `InvalidRoleDefinition`, not a `UnicodeDecodeError`.
- **`rp-uml2linkml` refuses workflows the service would refuse at start** (#259): it runs the
  library's own start-up check on the files it is about to write, and moves nothing (exit 1).
- **`rp-uml2linkml` names every read and write failure instead of a traceback** (#229): a
  missing model file, an unreadable or corrupt `.qea`, and an `--out` that cannot be written
  are one `rp-uml2linkml:` line each, exit 2. Reading a `.qea` no longer creates `-shm` or
  `-wal` files beside it, and an interrupted write leaves no report in `--out`.

## [0.11.0] - 2026-11-24

### ⚠ BREAKING
- **The UML converter writes explicit `required` and `multivalued` flags in a `slot_usage` whose
  limits differ** (`consumer-gap-fixes`, #304). A class that narrows an inherited `0..*` role to
  `1` now carries `multivalued: false` (and `required: false` for a `0..1` under a `1..1`), so
  `unique_key` can name it; before, the omitted flag inherited the parent's `true`. Regenerate
  converted schemas: every usage of a slot whose limits differ gets the explicit flags.
- **`Tenancy` takes `rules`, and `set_grants` refuses an undefined or system-only role**
  (`consumer-gap-fixes`, #306). `Tenancy(...)` has a new required keyword `rules: AccessRules`
  (the toolkit's own composition root passes its rules; a consumer that builds `Tenancy` directly
  must pass them). `Tenancy.set_grants` now runs `rules.validate_grants` after reading the record,
  so it refuses what `PUT …/grants` refuses (`UnknownRole`, `InvalidGrant`); the route no longer
  validates on its own and its 422 `invalid-body` answer is unchanged. Stored grants are not
  migrated: a set that drops a stored bad role is accepted. See "Grant and prohibit" in "Control
  access".

### Added
- **Absence filter** (`consumer-gap-fixes`, #312). `Session.find(cls, slot=None)` and the listing
  parameter `?absent=<slot>` (repeatable) match the aggregates with no value for the slot, and
  combine with every other filter; the listing's `total` counts them. A `None` inside a list is a
  `ValueError`. A slot with an `ifabsent` default is never absent. `Filter` and `Condition` gain
  `absent`. See "Listings and paging" in the HTTP API reference.
- **`state_iri` is public** (`consumer-gap-fixes`, #311). A consumer imports it from
  `rdf_persistence` to build a workflow state IRI, as the workflow how-to shows.
- **An aggregate validator reads a referenced aggregate** (`aggregate-guards` stage 1, #305,
  #334). `await reader.aggregate(iri)` returns the generated model as the transaction leaves it,
  or None when it is missing, removed earlier in the transaction, or not readable by the writer.
  A read pins the aggregate's version: the commit fails as a `Conflict` naming it if it changed
  meanwhile. See "Control access".

### Changed
- `Session.find(cls, slot=None)` now matches the aggregates with no value for the slot; it matched
  nothing before.
- `absent` is a reserved listing name, like `limit`, `offset` and `sort`: a model slot named
  `absent` can no longer be filtered or sorted on in a listing. Rename the slot.

## [0.10.0] - 2026-11-24

### ⚠ BREAKING
- **A slot over an abstract aggregate root is now generated as an IRI** (#303, #314). In a
  consumer's generated code such a slot changes from the embedded class to `str` (Python),
  `string` (TypeScript) and `sh:nodeKind sh:IRI` (shapes); the runtime mapper reads it as an IRI.
  No valid instance could have used the embedded form. An abstract root whose concrete kinds
  declare different identifier slots is now refused. See "Fixed" below for the cause.

### Added
- **Value modules for never-stored domain values** (`domain-values-and-fixes`, #301, #313). A
  fourth module kind, `module_kind: value`, generates the classes and enums that pure domain logic
  returns (a status, a finding, a report) into `<pkg>.domain.generated[.<group>]`. Their classes
  skip the stored-class rules. A domain or technical module may import a value module; a value
  module may import only domain, value and toolkit modules. A value class is never a root, and no
  stored class holds one; a stored class may use a value enum. A technical target that imports a
  value module gets its classes from the value package. See "Value modules" in "Model to code".
- **`expected_version` and `matched_version` are public** (#300, #316). A consumer's own route
  imports them from `rdf_persistence` and reads `If-Match` with the toolkit's rules: one strong
  tag gives its version; a missing header, a list or `*` gives 428; a weak tag gives 409.

### Fixed
- **A slot over an abstract aggregate root is a reference** (#303, #314). The abstract root had
  no identifier slot of its own (its concrete kinds take one from `Described`), so the generators
  read the slot as inlined. `load_schema` and `apply_defaults` now give the abstract root its
  kinds' identifier slot, so the runtime and every generator agree.
- **The testkit and the context honour `slot_usage`** (#302, #315). The aggregate strategy draws
  the value an `equals_string` or `equals_string_in` narrowing fixes. A class whose `slot_usage`
  changes a slot's `multivalued` gets a type-scoped JSON-LD term, so framing returns a list where
  the class holds one (and one value where it holds one). This also fixes the framed JSON the API
  serves for such a class.

> **On upgrade:** run `rp-generate` and commit the output. Code that built the embedded class for
> a slot over an abstract root now passes the referenced aggregate's IRI. The context can gain
> type-scoped terms for classes that narrow `multivalued` in `slot_usage`.

## [0.9.0] - 2026-11-22

### Added
- **Aggregate validators: a consumer's rules on any root's writes** (`aggregate-validators`).
  `install_service(aggregate_validators=...)` and `ServiceKit` take rules keyed by a schema class.
  They are checked at start-up: the key must be a class, not a mixin and not a toolkit class, and a
  root must derive from it. The write guard runs them last, on the old and new aggregate, with an
  `AggregateReader` that answers the classes of a member the writing caller may read. A refusal
  (`InvalidBody`, 422) stops the write before anything is stored. A rule that refuses the tenant
  root on create leaves no database or bucket. `AggregateValidator` and `AggregateReader` are
  exported. To support this, `open_session`, `Tenancy.tenant_session` and the session take an
  optional `may_read` check (`Session.may_read`); existing calls keep working. See "Enforce
  your own rules on aggregate writes" in "Control access".
- **`rp-uml2linkml` converts drawn role definitions and workflows** (`uml-roles-and-workflows`,
  #245 parts 2 and 3). Role definitions drawn as EA objects become the roles file that
  `load_role_definitions` reads. Each Statechart becomes `workflows/<name>.workflow.yaml`, which
  `load_workflow` reads; a transition's roles must be drawn role definitions. Constructs the
  converter does not support fail the run and name the node, diagram or transition. Workflow files
  are staged and read back before anything moves, and the consumer's other files in `workflows/`
  are kept. See "UML conventions".
- **`Relay.paused()`** holds the event relay still: committed activities stay pending while the
  block is open, and the relay runs one round after it.
- **The event-bus conformance suite can poll faster:** `run_case(..., poll_seconds=...)`.

### Fixed
- **A new tenant's root may own parts** (#276, #288). Tenant create answered
  `422 <part>.id: Field required` for a root owning a part. It now mints each owned part's IRI,
  nested parts included, from the part template, as an ordinary create does. A part that names its
  own `id` in the create body is refused with 422.
- **A business identifier on `dcterms:identifier` is accepted** (#277, #289). The toolkit's `id`
  slot shares the property and gave every class shape a property shape asking for an IRI, so a
  string identifier was refused as "not an IRI". The identifier slot no longer takes part in
  property resolution; the node itself stays `sh:nodeKind sh:IRI`.
- **A module's own slot wins over a toolkit slot of the same name** (#278, #289). A module slot
  named `version` (`dcat:version`) resolved to the toolkit's internal `version` depending on import
  order, so a value was dropped silently or every write was refused. Every view now keeps the
  application's slot when no toolkit class carries the toolkit's one. When a toolkit class does
  carry it, the clash is a hard-check problem, `toolkit_slot_name`, that names both definitions.
- **`rp-uml2linkml` fixes `member_class` only below an abstract collection** (#274, #287). An
  abstract reference collection whose concrete subclasses draw their own `dct:hasPart` role keeps
  the toolkit's `has_part`; each subclass fixes its own member class. Before, the two fixed values
  contradicted each other and `rp-generate --check` failed. A subclass member class that does not
  descend from the parent's is a `toolkit_slot` problem.

### Changed
- **Shapes are parsed once per process** (`api`). A second `Documents` over the same shapes reuses
  the parsed triples (keyed by their digest), and the warm-up runs once per process: building the
  toy service takes about a third of the time it did.

> **On upgrade:** run `rp-generate` and commit the output. The shapes change for every class
> (no `id` property shape), and so can the context and the lock. A schema that reuses the name of
> a slot a toolkit class carries now fails the hard check (`toolkit_slot_name`), so rename the
> slot. Tenant-create bodies must leave part `id`s out.

## [0.8.1] - 2026-11-21

### Fixed
- **A subclass whose `is_a` parent is in another module imports** (#242, #249). The parent is now
  the first Python base wherever it is declared; before, an imported parent came after the mixins it
  already has, and the module failed to import (no consistent MRO). In existing output, only a class
  whose parent sits in another module changes its base order, and with it its field order.
- **A schema class named like a library name no longer shadows it** (#243, #249). Generated modules
  import the capitalised `pydantic`, `typing`, `decimal` and `enum` names under `_` aliases
  (`_Field`, `_Optional`, `_BaseModel`, `_Decimal`, `_Enum`, …), so a class named `Field` or
  `Optional` is safe. The unused `LinkMLMeta` class is no longer generated. Regenerating changes
  every generated module; nothing outside them refers to the new names.
- **`rp-generate` checks the Python it writes** (#249). A run imports every generated module, and
  `rp-generate --check` also runs mypy over the generated packages; either failure names the module
  (or file and line) and the error, and the run exits 1. A run that used to report "no problems"
  for unimportable output now fails, including two modules that import each other (#208). mypy
  joins the `generate` extra; `make check-generated` type-checks too.
- **A dependent record of a root the same commit removes is refused** (#226, #251). Adding or
  replacing a dependent record (such as a comment's `has_target`) on a root the commit also removes
  raises `Conflict`, naming the record and the root, before anything is sent. Before, depending on
  the order, the record was dropped and reported as "removed by someone else", or stored dangling.
- **`assert_public_imports` guards `rdf_persistence_generation` too** (#200, #251): any submodule
  other than the package, its `testkit` and that testkit's plugins is refused and named.
- **`rp-uml2linkml` carries a collection's member class and a package's module kind** (#241, #245
  part 1, #247). A reference collection's `dct:hasPart` role to another converted class becomes its
  `member_class`; roles to two different classes fail the run. A package's `module_kind` tagged
  value becomes the module's annotation (`domain` when absent); an unknown value, or merged packages
  with different kinds, fail the run. See "UML conventions".

## [0.8.0] - 2026-11-21

### Added
- **`rp-uml2linkml`: generate LinkML modules from a UML class model** (`uml-to-linkml`, #196). It
  reads an Enterprise Architect `.qea` model, applies the toolkit's rules (tenant and abstract roots,
  the toolkit's mixins and shared slots, tagged values as annotations and unique keys) and writes
  the schemas with a report of what it left out. See the how-to "Generate the model from UML" and
  the reference "UML conventions".
- **Nested reference collections** (`nested-collections`, #198). The `nests` slot lets a collection
  hold collections of its own kind; a save that makes a nesting cycle is refused, and
  `members(collection, deep=True)` reads the items of the whole tree. The member class of a
  collection that another one nests cannot change. `WriteGuard.prepare` takes a keyword-only
  `context: GuardContext`, so a write guard can rely on the versions it read.
- **Refuse deleting a referenced aggregate** (`delete-refuses-referenced`, #201). A class annotated
  `rp_on_referenced_delete: refuse` cannot be removed, by `session.remove` or the generic
  `DELETE`, while another aggregate points to it: the session raises `InUse`, naming the referrers,
  and the API answers `409` with the `in-use` problem type. A collection cascade over such a member
  is refused too. Without the annotation, deletion behaves as before.
- **Unique keys where absent values count as equal** (`unique-key-nulls-equal`, #202). A
  tenant-scoped unique key may set the LinkML field `consider_nulls_inequal: false`: an absent key
  slot then counts as one value, in the key guard and in `key_duplicates()`. Other scopes keep
  refusing the option.
- **A case-insensitive contains filter on listings** (`listing-contains-filter`, #203):
  `Session.find` takes the `Contains` operator, and the generated API offers a `<slot>~` parameter
  for every text slot; on any other slot it answers `400 bad-query`.
- **`testkit.open_event_stream`** (`testkit-event-stream`, #204) opens a tenant's event stream
  in-process for tests. The toolkit's lifespan sets `app.state.rp_lifespan_started` while it runs.

### Changed
- **BREAKING: reference collections state members with `dct:hasPart`** (`collection-has-part`, #199).
  The slot and field `had_member` (`prov:hadMember`) of `ReferenceCollection` is now `has_part`
  (`dcterms:hasPart`), in Python, JSON, TypeScript and the API: the listing filter `had_member`
  becomes `has_part`, and the sort keys `had_member` and `-had_member` become `has_part` and
  `-has_part`. `vocabulary.HAD_MEMBER` is now `vocabulary.HAS_PART`; there is no alias.
  - The toolkit's own schema goes to version 3. Its migration rewrites the stored members of every
    collection at start-up and on restore of a dump at version 2. Every version token is rotated
    once by the upgrade, so a client that holds one re-reads before it replaces, or the replace
    answers 409.
  - A consumer whose lock names a collection class migrates in three steps. (1) Raise the `version:`
    of your schema. (2) Run `rp-generate`: it drafts `<old>__<new>.yaml` with one
    `DROP <http://www.w3.org/ns/prov#hadMember>` step per collection class. (3) Keep or delete that
    step, since it matches nothing after the toolkit's 2 to 3 step, and commit the file and the
    lock. Without the raised version, `rp-generate` refuses and names the class. A consumer with no
    locked collection class only regenerates.
  - The mixin's class IRI changes from `prov:Collection` to `dcmitype:Collection`. The JSON-LD term
    `ReferenceCollection` and the target of the mixin's shape change; no stored data does, because
    no graph is typed with the mixin.
  - To state `dct:hasPart` elsewhere in a model, reuse the toolkit's `has_part` slot instead of
    declaring another slot with `slot_uri: dcterms:hasPart`.

## [0.7.0] - 2026-11-19

### Changed
- **BREAKING: a target's kind is derived from its modules, and its package must sit in a folder that
  kind allows** (`target-kind-from-the-model`). A target is `technical` when every module it
  generates is annotated `module_kind: technical`, and `domain` otherwise. The `kind` key of
  `[[tool.rp-generate]]` is gone, and an entry that still has it is refused as an unknown key. Rule
  `TARGET_KIND` now applies to every target, a consumer's included: the package has `domain` (a
  domain target) or `services`, `adapters` or `entrypoints` (a technical one) before `generated`,
  and a target that generates technical modules beside others fails, naming them. The toolkit's own
  theme check stays for its own targets. The toy library and the getting-started example moved to
  `domain/generated/`.
  - Migrate in three steps. (1) Package: change each `package` to
    `<your package>.<layer>.generated`, for example `app.generated` to `app.domain.generated`, and
    move the generated folder (`python`, `diagrams`) to match. (2) The `kind` key: delete it from
    every entry. (3) A technical module: annotate it `module_kind: technical` and put it in a target
    of its own whose package is in `services`, `adapters` or `entrypoints`; a technical module left
    unannotated is derived as `domain`, and the error says to annotate it. Then run `rp-generate`.

- **BREAKING: the domain model is generated per theme** (`domain-model-per-theme`). Each theme that
  owns domain concepts has its own `<theme>.domain.generated` package, and seven modules moved out
  of `rdf_persistence.core.domain.generated`:
  - `rp_access`, `rp_tenancy`: `rdf_persistence.core.domain.generated.<module>` →
    `rdf_persistence.access.domain.generated.<module>`
  - `rp_provenance` → `rdf_persistence.provenance.domain.generated.rp_provenance`
  - `rp_files` → `rdf_persistence.files.domain.generated.rp_files`
  - `rp_collections`, `rp_discussion`, `rp_workflow`:
    `rdf_persistence.core.domain.generated.<module>` →
    `rdf_persistence.collaboration.domain.generated.<module>`

  `rdf_persistence.core.domain.generated` keeps `rp_core` and `rp_annotations`;
  `rdf_persistence.core.domain.generated.rp`, the module that re-exported every class, is gone. The
  names exported from `rdf_persistence` are the same objects (148): only a deep import of a moved
  path breaks, with `ModuleNotFoundError`, and no old path keeps a re-export shim. The combined
  `shapes.ttl`, `context.jsonld` and frames stay in `core/domain/generated/` and are the ones to
  load; the new theme targets write partial copies beside their classes, which are not loaded.
  `rp_tenancy` generates in `access`, and `themes-ordered` ranks `files` above `provenance`. A
  consumer's generated code does not change; run `rp-generate` once and rewrite any deep import of
  a moved path.
- **A module beside the root that names another package is imported from it**
  (`domain-model-per-theme`). The generator imports a module in the root's folder from its own
  `python_package` when that differs from the root's, and on the toolkit's run checks that a toolkit
  target generates that package.
- **A stored file is recognised by `class_uri: rp:StoredFile`, not by the class name `StoredFile`**
  (`domain-model-per-theme`). A consumer's own stored-file mixin must declare that `class_uri`, or
  mix in the metamodel's `StoredFile`.

## [0.6.0] - 2026-11-19

### Added
- **Imports between generation targets** (`thematic-structure`): a schema that imports a module of
  another target, where that module declares `python_package`, imports its classes from
  `<python_package>.<module>` and does not generate them again; the manifest lists the imported
  YAML as an input. A module without `python_package` is generated as before.
- **A toolkit target's folder follows its kind** (`thematic-structure`): in the toolkit's own run,
  rule `TARGET_KIND` also refuses a target whose `package` does not have `domain` (for a `domain`
  target) or `services`, `adapters` or `entrypoints` (for a `technical` one) before `generated`,
  and a theme of the library (`rdf_persistence.<theme>.<layer>.generated`) before that layer.
  `rdf_persistence.testkit` and `rdf_persistence_generation` are exempt. A consumer's run is not
  checked.

### Changed
- **The library is organised in thirteen themes** (`thematic-structure`). Every module moved from
  `rdf_persistence/{domain,services,adapters,entrypoints}/` to
  `rdf_persistence/<theme>/<layer>/`: `core`, `iris`, `schema`, `files`, `provenance`,
  `persistence`, `migrations`, `access`, `tenancy`, `events`, `collaboration`, `messaging` and
  `api` (the map: `docs/modules/ROOT/pages/architecture/index.adoc`, "Where a module lives"). The names of `rdf_persistence`
  are the same objects (148 once `mint_aggregate_iri` is removed, see Removed); only a deep import
  of an old module path breaks, with `ModuleNotFoundError`, and no old path keeps a shim:
  `rdf_persistence.services.session`, `rdf_persistence.services.messagebus`,
  `rdf_persistence.services.{events,event_hub,event_stream,relay}`,
  `rdf_persistence.services.{collaboration,discussion,reference_collections,transitions,workflows,write_guards}`,
  `rdf_persistence.adapters.redis_events` or `rdf_persistence.entrypoints.kit` are gone. The
  metamodel's generated package moved from `rdf_persistence.domain.generated` to
  `rdf_persistence.core.domain.generated`.
- **The technical schemas are split by theme** (`thematic-structure`). `model/technical/{service,
  settings,telemetry,templates,wire}/` are now `model/technical/<theme>/rp_<theme>_<layer>.yaml`
  (`rp_<theme>_settings.yaml` or `rp_<theme>_templates.yaml` for a non-served group), each generated
  into `rdf_persistence/<theme>/<layer>/generated/` (a group into `generated/settings/` or
  `generated/templates/`; `testkit` is unchanged). The
  top-level names are unchanged; a deep import moves:
  - from `rdf_persistence.services.generated.service.rp_service`: `ServiceSettings`, `IriPolicy`,
    `IdSpec`, `IdKind` to `rdf_persistence.iris.services.generated.rp_iris_services`; `Page`,
    `Filter`, `ListRequest`, `Condition`, `ListPlan`, `AggregateHead` to
    `rdf_persistence.persistence.services.generated.rp_persistence_services`; `Migration`,
    `MigrationStep` to `rdf_persistence.migrations.services.generated.rp_migrations_services`;
    `VerifiedCaller`, `GrantSet`, `CallerAccess`, `AccountSummary` to
    `rdf_persistence.access.services.generated.rp_access_services`; `TenantDump`, `TenantSummary`
    to `rdf_persistence.tenancy.services.generated.rp_tenancy_services`; `EventEnvelope` to
    `rdf_persistence.events.services.generated.rp_events_services`; `Referrer`, `ReferrerList`,
    `MemberList` to `rdf_persistence.collaboration.services.generated.rp_collaboration_services`;
    `TenantCreate`, `LabelUpdate`, `Authorised`, `Problem`, `ProblemKind`, `ProblemSlug` to
    `rdf_persistence.api.entrypoints.generated.rp_api_entrypoints`;
  - from `rdf_persistence.services.generated.settings.rp_settings`: `HttpSettings` to
    `rdf_persistence.core.services.generated.rp_core_services`; `LimitSettings` to
    `rdf_persistence.persistence.services.generated.settings.rp_persistence_settings`;
    `JwksSettings` and `DirectorySettings` to
    `rdf_persistence.access.services.generated.settings.rp_access_settings`; `EventSettings` to
    `rdf_persistence.events.services.generated.settings.rp_events_settings`; `SseSettings` and
    `ToolkitSettings` to `rdf_persistence.api.entrypoints.generated.settings.rp_api_settings`;
  - `LogContext`, from `rdf_persistence.services.generated.telemetry.rp_telemetry`, to
    `rdf_persistence.core.services.generated.rp_core_services`; the SPARQL term bundles, from
    `rdf_persistence.services.generated.templates.rp_templates`, to
    `rdf_persistence.schema.services.generated.templates.rp_schema_templates`, and
    `IriTemplateVariables`, `IriParts` to
    `rdf_persistence.iris.services.generated.templates.rp_iris_templates`;
  - from `rdf_persistence.adapters.generated.rp_wire`: the `Zitadel*` records, `JwtClaims`,
    `DiscoveryDocument` and `BadRequestMeans` to
    `rdf_persistence.access.adapters.generated.rp_access_adapters`; `FusekiDatasetList` and
    `FusekiDataset` to `rdf_persistence.persistence.adapters.generated.rp_persistence_adapters`.
- **The served types come from eight schemas** (`thematic-structure`). `/openapi.json` is
  unchanged. `rp_service.ts`, which every consumer's TypeScript output carries, holds the same
  declarations in a new order: that of the served schemas (`iris`, `persistence`, `migrations`,
  `access`, `tenancy`, `events`, `collaboration`, `api`).
- **A consumer's generated code imports `RpModel` from `rdf_persistence`** (`thematic-structure`),
  where it named `rdf_persistence.domain.base`. Its freshness check fails once after the upgrade:
  run your regenerate command.
- **`FusekiStore` is built on `SparqlProtocolStore`** (`thematic-structure`), a base in
  `rdf_persistence.persistence.adapters.sparql_protocol` that holds the SPARQL 1.1 Protocol;
  neither is a new public name, and `FusekiStore` behaves and is built as before. Its error
  messages name its `service` ("Fuseki"), so they read as before.
- **BREAKING for log readers: logger names follow the new module paths** (`thematic-structure`).
  Each module logs under `__name__`, so a configuration on an old name no longer matches; one on
  `rdf_persistence` still does. Old → new:
  `rdf_persistence.adapters.fuseki` → `rdf_persistence.persistence.adapters.sparql_protocol`;
  `adapters.redis_events` → `events.adapters.redis_events`; `adapters.s3` → `files.adapters.s3`;
  `adapters.zitadel` → `access.adapters.zitadel`; `entrypoints.kit` → `api.entrypoints.kit`;
  `entrypoints.problems` → `api.entrypoints.problems`; `services.file_removal` →
  `api.services.file_removal`; `services.iri_policy_guard` → `tenancy.services.iri_policy_guard`;
  `services.messagebus` → `messaging.services.messagebus`; `services.migration_runner` →
  `tenancy.services.migration_runner`; `services.relay` → `events.services.relay`;
  `services.session` → `persistence.services.session`; `services.sweep` →
  `tenancy.services.sweep`; `services.tenancy` → `tenancy.services.tenancy`;
  `services.tenant_dump` → `tenancy.services.tenant_dump`; `services.tenant_sweep` →
  `tenancy.services.tenant_sweep` (each under `rdf_persistence.`).
- **The store's 400 log line** (`thematic-structure`): "Fuseki refused a request with 400" is now
  "A SPARQL Protocol store refused a request with 400", under the logger
  `rdf_persistence.persistence.adapters.sparql_protocol`. `BAD_QUERY_MESSAGE` and `UNREADABLE` are
  no longer in the new module, and no old module keeps them (see Removed).
- **`error.type` names the new module** (`thematic-structure`): the attribute is the exception's
  module and class, so `rdf_persistence.domain.exceptions.Conflict` is now
  `rdf_persistence.core.domain.exceptions.Conflict`, and so for every toolkit exception. A
  dashboard or alert that matches the old value must change.
- **The documentation is restructured** (#180, #182) into a tutorial, a user manual, guides and
  the specification; `howto/adopt.adoc` is split into `user-manual/*` pages (its old address
  redirects), and `make check-docs` resolves every `xref` and its anchor.
- **`rp-generate --help` names the real configuration keys** (#182), and the description of
  `max_document_nodes` says what it limits. The tests' example IRI policy is generic.

### Removed
- **BREAKING: the four generator testkit shims** (`generator-package`, #165). The modules
  `rdf_persistence.testkit.{freshness,conformance,roundtrip,strategies}` are gone, and so are the
  names `Conformance`, `conformance_problems`, `round_trip` and `aggregate` of
  `rdf_persistence.testkit`: an import of an old path fails with `ModuleNotFoundError`. Use
  `rdf_persistence_generation.testkit.*` (`pytest_plugins =
  ["rdf_persistence_generation.testkit.freshness"]`). `assert_isomorphic` stays in
  `rdf_persistence.testkit.graphs`. The contract `library-never-imports-the-generator` now has no
  ignored edge.
- **BREAKING: `rdf_persistence.domain.base`, `rdf_persistence.adapters.fuseki` and
  `mint_aggregate_iri`** (`thematic-structure`). No release ever shipped them as deprecated: they
  are removed in the release that ships the move, with no deprecation period.
  - `rdf_persistence.domain.base` is gone (`ModuleNotFoundError`), and with it the `domain/` and
    `adapters/` folders at the top of the package. `RpModel` is the same class: import it with
    `from rdf_persistence import RpModel` (it is defined in `rdf_persistence.core.domain.base`). A
    consumer's old generated code that names `rdf_persistence.domain.base` fails at import: run
    your regenerate command. The model guard still names a class derived from the old path.
  - `rdf_persistence.adapters.fuseki` is gone: import `FusekiStore` from `rdf_persistence`, or from
    `rdf_persistence.persistence.adapters.fuseki`. The module's other names are not re-exported:
    the SPARQL Protocol constants (`SPARQL_QUERY`, `SPARQL_UPDATE`, `RESULTS_JSON`, `GRAPH_PARAM`)
    are in `rdf_persistence.persistence.adapters.sparql_protocol`; `BAD_QUERY_MESSAGE` and
    `UNREADABLE` have no module that holds them any more.
  - `mint_aggregate_iri` is removed with its top-level export, so `rdf_persistence.__all__` holds
    148 names. Call `Iris.mint_aggregate` on the service's `Iris`
    (`DEFAULT_IRIS.mint_aggregate(tenant, cls_type="", rp_path=path)` mints the same IRI).
- **The eleven IRI wrappers that only called `DEFAULT_IRIS`** (`thematic-structure`), from
  `rdf_persistence.services.iris` (none was a top-level name): `mint_tenant_iri`, `tenant_iri`,
  `aggregate_iri`, `is_aggregate_iri`, `is_aggregate_graph_iri`, `is_loaded_graph_of`,
  `mint_part_iri`, `loaded_graph_iri`, `tenant_resource_name`, `principal_iri` and the helper
  `_default_iris`. Call the `Iris` of the service instead (`mint_tenant`, `tenant`, `aggregate`,
  `is_aggregate`, `is_aggregate_graph`, `is_loaded_graph`, `mint_part`, `mint_loaded_graph`,
  `resource_name`, `principal`). `Iris.resource_name` takes the tenant's IRI, not its id, and reads
  the id through the policy, so it is stricter than `tenant_resource_name(prefix, id)`; a bad tenant segment is refused by `ServiceSettings` (`ValidationError`), where a wrapper raised
  `InvalidIri`. The twelve layout functions that no policy changes stay, in
  `rdf_persistence.iris.domain.layout`.

### Fixed
- **The generator's guards are harder to fool** (#164): the check that library tests never load
  the generator reads every form of `pytest_plugins`, `__import__` and `importorskip`;
  `rp-generate --list-python-folders` works without `linkml` installed; the freshness report names
  a stale generator module once, with the targets it affects, instead of once per target.

## [0.5.0] - 2026-11-18

### Added
- **A generation target declares its `kind`** (`technical-models`): the optional `kind` key of a
  `[[tool.rp-generate]]` entry is `domain` or `technical`; `rp-generate` fails, naming the target
  and the module, when a technical target holds a module not annotated `module_kind: technical`,
  or a domain target holds one annotated `technical`. A target without `kind` generates as before.
- **The toolkit's deployment values are settings** (`technical-models`): `HttpSettings`,
  `JwksSettings`, `DirectorySettings`, `EventSettings`, `SseSettings` and `LimitSettings`, held
  together by `ToolkitSettings`, are generated from `model/technical/settings/rp_settings.yaml` into
  `rdf_persistence.services.generated.settings` and exported from `rdf_persistence`. Every value
  defaults to the one the toolkit used before, with bounds (a zero timeout, a shared-secret
  algorithm or a leeway outside 0 to 300 seconds is refused). Each adapter and service takes its
  group as a constructor argument; `ServiceKit` and `install_service` take `toolkit=` and hand each
  object it builds its group.
- **`settings_from_env`** reads any generated settings model, `ToolkitSettings` included, from
  environment variables (`RP_HTTP__READ_TIMEOUT_SECONDS=60`), validated once through the model. It
  needs the new `settings` extra (`rdf-persistence[settings]`, pydantic-settings); importing the
  toolkit reads no variable and loads no dotenv file.
- **Generation: `default_instance` and list defaults** (`technical-models`): a slot annotated
  `default_instance: 'true'` defaults to a fresh instance of its range class (checked by a hard
  rule: the range must be a class that can be built with no argument and be declared first); the
  `ifabsent: string(a, b, ...)` of a multivalued slot is generated as the list `['a', 'b']`, where
  the stock generator wrote the one string.
- **`fill_terms` and `fragment_terms`** (`rdf_persistence.domain.sparql`): they fill a query
  template from a bundle of `SparqlTerm` fields and render a fragment from one.
- **Generation: `field_name: slot`** (`technical-models`): a slot annotated `field_name: slot` (a
  `GenerationAnnotation`) is named after the slot in Python and in the JSON-LD context, and keeps its
  alias. Every other field keeps its name.
- **Generation: `python_import`** (`technical-models`): a LinkML type annotated `python_import`
  with a module name, together with `repr`, generates its field as the `repr` class imported from
  that module.
- **Four more RDF representations** (`manual-revision-notes`): a route that answers one aggregate
  also serves N-Triples, N-Quads, TriG and RDF/XML, chosen by `Accept`; a listing stays JSON and
  JSON-LD. RDF/XML is 406 for a predicate with no XML local name or a value XML 1.0 cannot hold,
  and on a create or replace that 406 comes before anything is written. The LinkML `RdfFormat`
  enum declares each serialisation's media type.
- **`If-Match` takes `*` and a list of tags** (`manual-revision-notes`, RFC 9110 §13.1.1).
- **The token verifier's algorithms and leeway are configurable** (`manual-revision-notes`):
  RS, PS and ES 256 to 512 and EdDSA by default, `none` and shared-secret algorithms always refused,
  with a leeway on `exp` and `nbf` (about 30 s by default); through `JwksSettings` since
  `technical-models`. Each key is bound to the token's algorithm, and only signature keys verify.
- **Tracing through the OpenTelemetry API** (`otel-observability`): spans around every store call,
  the commit, the migrations, both sweeps, the relay rounds and the message bus's handlers and
  observers. They are no-ops until the application installs a provider; a span records an
  exception's type, never its message. `opentelemetry-api>=1.44,<2` is a declared dependency.
  `RedisEventBus(middlewares=...)` lets the application add FastStream's broker telemetry. The
  how-to "See what the toolkit is doing" (`howto/observability.adoc`) shows the set-up.
- **One log context** (`otel-observability`): `LogContext`, generated from
  `model/technical/telemetry/rp_telemetry.yaml`, names every log attribute after the OpenTelemetry
  semantic conventions (`db.*`, `error.type`, `messaging.*`) plus an `rp.*` namespace.
- **The generator is its own top-level package** (`generator-package`): `rdf_persistence_generation`,
  shipped in the same wheel behind the `generate` extra. The library never imports it, and the
  generator has its own unit, feature, integration and end-to-end tests (`make test-generator`).
- **The metamodel says where its classes live** (`generator-package`): each toolkit schema module
  declares `python_package`, and `rp.yaml` its `public_package`; the generator reads them in place
  of two hard-coded constants and checks them with two hard rules.
- **Decision records** (`manual-revision-notes`): ADR-001 to ADR-005 (own SPARQL client, own JWKS
  cache, FastAPI rather than connexion, signing algorithms, representations), and a contract test
  of every operation against the served OpenAPI (schemathesis).

### Changed
- **A `SparqlTerm` model field refuses a raw `str`** (`technical-models`): a field of that type
  raises a `ValidationError` when built with a plain string, before any query text is made. Build
  the term with the `domain.sparql` factories.
- **`ZitadelUserState` is a generated enum** (`technical-models`): the six user states of a Zitadel
  answer. A user state outside the six makes the directory answer unreadable
  (`IdentityUnavailable`) where the adapter accepted any string before.
- **`[[tool.rp-generate]]` keys are unchanged** (`technical-models`): the keys of a target are read
  as before; `field_name: slot` (Added) is the only new way to name a field after its slot.
- **BREAKING for a deployment that sets such a value: the settings are bounded tighter**
  (`technical-models`). Every duration is at most one year (31,536,000 seconds; an infinite or
  larger value is refused), `unknown_kid_cooldown_seconds` is at least 1 second (it was 0.001),
  and `JwksTokenVerifier` refuses a cooldown longer than `ttl_seconds`. A deployment that keeps the
  defaults is not affected. `settings_from_env` no longer repeats the input value in a
  `ValidationError`.
- **BREAKING: the testkit's records moved to `rdf_persistence.testkit.generated`**
  (`technical-models`). `ClassShape`, `SlotShape`, `ContainerMarker`, `Violation`, `MachineUser`,
  `ZitadelProject`, `ZitadelServer`, `ExecResult`, `FusekiServer` and `GarageServer` are generated
  from `model/technical/testkit/rp_testkit.yaml` and are imported from
  `rdf_persistence.testkit.generated.rp_testkit`, no longer from
  `rdf_persistence.generation.generated.rp_generation`; there is no shim. A new `FieldFlags`
  record (`required`, `multivalued`) is what the model-shape test compares. `ConstraintCase`,
  `ConstraintKind` and `GenerationTarget` stay in `rp_generation`.
- **BREAKING: the per-value keywords and constants the settings replace are removed**
  (`technical-models`). A caller that passes an old keyword gets a `TypeError` from every constructor, except `bootstrap`,
  which takes dependencies by keyword: `bootstrap(limit=...)` raises `ValueError` ("no handler or
  observer names the dependency limit"), or binds to a handler that declares a `limit` dependency.
  One that imports an old constant gets an `ImportError`. Pass the group instead:
  - `JwksTokenVerifier(algorithms=, leeway_seconds=)` is now `jwks=JwksSettings(allowed_algorithms=,
    leeway_seconds=, ...)`;
  - `RedisEventBus(stream=, retention=, claim_idle=)` is now `events=EventSettings(stream=,
    retention_seconds=, claim_idle_seconds=, ...)`;
  - `Relay(interval=, publish_timeout=)` is now `events=` (`relay_interval_seconds`,
    `publish_timeout_seconds`), and `EventHub(max_queue=)` is `events=` (`hub_queue_size`);
  - `MessageBus(limit=)` and `bootstrap(limit=)` are now `limits=LimitSettings(max_messages=)`;
  - `Mapper(max_roots=)` and `UnitOfWork(max_roots=)` are now `limits=LimitSettings(max_roots=)`
    on the `Mapper`; `UnitOfWork` reads it from the mapper and takes no limit of its own;
  - `add_events_route(access_ttl=, keep_alive=, resume_window=, max_lifetime=)` is now
    `sse=SseSettings(access_ttl_seconds=, keep_alive_seconds=, resume_window_seconds=,
    max_lifetime_seconds=)`;
  - `FusekiStore`, `JwksTokenVerifier`, `ZitadelIdentity` and `S3FileStore` take `http=HttpSettings(...)`
    (connect and read timeouts, attempts), and `ZitadelIdentity` also `directory=DirectorySettings(page_size=)`;
  - `Documents` takes its node limit, and `tenant_dump.restore` its manifest cap, from
    `limits=LimitSettings(max_document_nodes=, max_manifest_bytes=)`;
  - removed constants: `CONNECT_TIMEOUT_SECONDS` and `READ_TIMEOUT_SECONDS` (`adapters/_http.py`,
    `adapters/s3.py`), `MAX_ATTEMPTS` (`adapters/s3.py`), `JWKS_TTL_SECONDS`,
    `UNKNOWN_KID_COOLDOWN_SECONDS`, `DEFAULT_ALGORITHMS`, `DEFAULT_LEEWAY_SECONDS` and
    `MAX_LEEWAY_SECONDS` (`adapters/jwks.py`), `POLLING_INTERVAL_MS` (`adapters/redis_events.py`),
    `PAGE_SIZE`, `ACTIVE_STATE` and `INACTIVE_STATE` (`adapters/zitadel.py`), `MAX_LIFETIME`,
    `ACCESS_TTL`, `KEEP_ALIVE_SECONDS` and `RESUME_WINDOW` (`entrypoints/sse.py`), `MAX_NODES`
    (`services/documents.py`), `DEFAULT_MAX_ROOTS` (`services/mapper.py`), `MAX_MANIFEST_BYTES`
    (`services/tenant_dump.py`), `FIELD_OF_TOML_KEY` and `TOML_KEY_OF_FIELD`
    (`generation/config.py`; the aliases of `GenerationTarget` replace them); their values are the defaults of the groups;
  - the Zitadel slugs `PROJECTS`, `MACHINE_USERS`, `OWN_ORGANISATION` and `TOKEN_PATH`, only the
    testkit used, moved from `rdf_persistence.adapters.zitadel` to `rdf_persistence.testkit.zitadel`.
- **BREAKING: the technical models moved out of the domain layer** (`technical-models`). Every
  name still imports from `rdf_persistence`; only a deep import of an old module path breaks, with
  `ModuleNotFoundError`:
  - `rdf_persistence.domain.generated.service` is now `rdf_persistence.services.generated.service`
    (the service records, loaded lazily from the top level);
  - `rdf_persistence.domain.iris` is now `rdf_persistence.services.iris` (the IRI policy, `Iris`,
    `DEFAULT_IRIS`, `IdSource`, `mint_aggregate_iri`) and `rdf_persistence.domain.layout` (the
    fixed IRI and name layout functions, free of the policy);
  - `rdf_persistence.domain.tenant_move` is now `rdf_persistence.services.tenant_move`;
  - the schemas `model/service/` and `model/adapters/` are now `model/technical/service/` and
    `model/technical/wire/`; the domain schemas `model/rp_*.yaml` stay where they are, and a
    consumer schema still imports `rdf_persistence/model/rp_core` (no technical schema can be
    imported that way).
- **BREAKING: the generator moved to `rdf_persistence_generation`** (`generator-package`).
  `rdf_persistence.generation` is gone, with no shim; import the generator from
  `rdf_persistence_generation`, and the `rp-generate` entry point is
  `rdf_persistence_generation.cli:main`. Every manifest's input paths change, so run your
  regenerate command once after upgrading (`howto/adopt.adoc#upgrade-generator-package`). The
  testkit's freshness plugin, conformance suite, round-trip check and strategies moved to
  `rdf_persistence_generation.testkit`; their old paths in `rdf_persistence.testkit` warn and go in
  0.6.0 (#165). `assert_isomorphic` stays in `rdf_persistence.testkit.graphs`.
- **BREAKING for log readers: log attributes and messages** (`otel-observability`). Attribute names
  follow `LogContext` (`step` is `rp.step`, `tenant` is `rp.tenant.id`, ...) and every message is a
  constant; there are no aliases. `howto/observability.adoc` lists the old and new names. The
  library logs an error only where it handles it, so `MessageLimitExceeded` is logged once.
- **BREAKING: `FusekiDataset.ds_name` is now `fuseki_dataset_name`** (`otel-observability`): the
  generator names a field after its slot when the alias is no Python name.
- **BREAKING: `If-Match` is compared strongly** (`manual-revision-notes`): `W/"v"` is now 409 and
  an unquoted `v` 428 (both matched before); `expected_version` refuses `W/`, `*` and lists.
- **BREAKING: Accept** (`manual-revision-notes`). Parsing is python-mimeparse's (a new dependency,
  `python-mimeparse==2.0.0`): an unparsable or empty `q` reads as 1 (it read as 0) and a `q` above 1
  as 1 (it outranked `q=1`). A wildcard or a type range can now be answered with one of the four new
  serialisations where it was 406; a client that refuses every type by name must name the new ones
  too.
- **BREAKING: a language-tagged value keeps its tag in JSON-LD** (`manual-revision-notes`): it is a
  value object, where it lost the tag before; JSON still shows a plain string.
- **BREAKING: JSON-LD is read on one path, PyLD's** (`manual-revision-notes`). A body or loaded file
  with an invalid IRI, or that is not a JSON object or array, is refused where it gave fewer or no
  triples. A loaded file that names a graph or uses a relative IRI without `@base` is refused with
  `InvalidGraph`, and such a body with `InvalidBody`; those triples were dropped without a word.
- **BREAKING: token checks** (`manual-revision-notes`): `jwks.ALLOWED_ALGORITHMS` and `jwks.ES256`
  are removed (the algorithms are `JwksSettings.allowed_algorithms`), and a token expired by less
  than the leeway is now accepted.

### Fixed
- **Reference collections honour the mapper's `max_roots`** (`manual-revision-notes`); they used the
  default limit.
- **Models are built with keyword arguments, not `model_copy(update=...)`**
  (`manual-revision-notes`), so a misspelt field fails validation instead of being ignored.
- **rdflib's SPARQL parsing is safe across threads** (`manual-revision-notes` follow-ups): parsing
  goes through locked wrappers, which an import contract enforces; concurrent requests could fail
  in pyparsing before.
- **The RDF writers run off the event loop**, in a worker thread.
- **The OpenAPI document** gives the generated component schemas their `type` (#148) and each
  server-sent event its shape (#153).
- **A hung test times out with a signal**, so a test worker never crashes.

## [0.4.0] - 2026-11-16

### Added
- **Several stores** (`tenant-stores`): `install_service(..., stores={name: store})` wires named
  stores beside the default one; each tenant's access record names its store, and the kit routes
  the tenant's sessions, sweep and migrations there. A record naming a store the service does not
  wire raises `StoreNotWired`.
- **Events across deployments** (`aggregate-events`): every recorded activity is the outbox entry;
  a relay that runs with the service publishes it, as the generated JSON with a JSON-LD context
  link (`context_link`), to an `EventBus` (`install_service(..., event_bus=...)`). Incoming events
  of other deployments go to the message bus (`Receive`). The Redis Streams bus on FastStream is
  the optional extra `events` (`rdf-persistence[events]`). A tenant's events can be followed over
  server-sent events, resuming with `Last-Event-ID` within 7 days; the stream shows only what the
  caller may read. Exported: `EventBus`, `EventEnvelope`, `Receive`, `context_link`.

### Fixed
- **A literal holding `\u` is stored as sent** (#108): a backslash followed by `u` or `U` was
  read by the store as a code-point escape.
- **A failed tenant create or restore cleans up only what it made.**
- **Event logs carry no tenant values** (#125).

## [0.3.0] - 2026-11-15

### Added
- **Atomic commits** (`atomic-commit`, #83): `session.transaction()` commits the writes to several
  aggregates of one tenant as one guarded update request, all or nothing. `UnitOfWork` gained
  `remove`, `version` and `discard`. A commit is limited to 500 roots by default (`CommitTooLarge`,
  413); `commit(batches=True)` takes a larger one in several transactions.
- **Unique keys across aggregates** (`cross-aggregate-unique-keys`): a scoped `unique_keys`
  declaration is enforced at commit; a clash raises `KeyConflict` (409 `key-conflict`), and
  `Session.key_duplicates()` reports the values a tenant's aggregates already repeat.
- **Collaboration** (`collaboration-and-reference-collections`, #78–#81), through the
  `Collaboration` service opened from the kit: the aggregates that refer to a resource
  (`referrers`); reference collections by list or by rule (`ReferenceCollection`, `members`),
  guarded on every write and deleted with their members; comments and replies on any aggregate
  with the `annotate` action; workflows read from files, with a toolkit-owned state and recorded
  transitions (`Workflows`, `transition`, `transitions`).
- **Dump and restore a tenant** (`tenant-dump-restore`): `kit.dump_tenant` writes the tenant's
  database as N-Quads with a `TenantDump` manifest; `kit.restore_tenant` restores it into a new
  tenant, rewriting the tenant id in every IRI.
- **Application data** (`app-level-data`): one application database, `{prefix}-app`, for data that
  belongs to no tenant. A class annotated `database: application` lives there; open it with
  `kit.application_session` after `kit.require_application`.
- **Message bus and provenance** (`message-bus`): every commit records one PROV activity (`Add`,
  `Replace`, `Remove`, or the toolkit's and the application's own commands) with a `Generation` or
  `Invalidation` per aggregate, in the tenant's provenance graph. `MessageBus` and `bootstrap`
  hand a command to its nearest handler and the committed activity to its observers along the
  class hierarchy. `RecordingObserver` in the testkit.
- **Schema migrations** (`schema-migrations`): `rp-generate` keeps a schema lock and writes
  migration files; each database is stamped with its schema version and migrated at start-up
  (`MigrationFailed`, `TenantBehind`); a restore migrates a dump from an older version of the
  chain.

### Changed
- **BREAKING: commits are all or nothing.** A unit of work that touches several aggregates either
  commits all of them or none; before, each aggregate committed on its own.
- **BREAKING: every commit writes a provenance graph** (`<tenant>/provenance`). Tests that compare
  a whole dataset will see it.
- **BREAKING: `TransitionRecord` is replaced by `Transition`.** Records written by an earlier
  `develop` build are no longer read by `transitions()` and are kept when their aggregate is
  deleted.
- **BREAKING: `install_service` and `ServiceKit` require `migrations`**, the folder of the
  application's migration files.
- **BREAKING: a restore refuses a dump whose schema stamps are outside the service's chain**; a dump
  made before the stamps existed no longer restores.

### Fixed
- **The tenant root is found whatever string type its IRI has** (#76).

## [0.2.0] - 2026-11-13

### Added
- **IRI policy** (`iri-policy`, #26): `ServiceSettings.iri_policy` sets the template and id kind
  of every IRI the toolkit mints: tenants, aggregates, parts, loaded graphs, access records, meta and
  registry graphs, and principals (short random ids, flat IRIs, a `{type}` from the class or its
  `rp_iri_type`, a `{deployment}` segment). One `Iris` per service mints and checks them; ownership
  follows the stored graph and the registry, not IRI nesting. At start-up the effective policy is
  recorded in the system database, and a later start under another policy refuses with
  `IriPolicyChanged` naming the fields. Exported: `Iris`, `IriPolicy`, `IdSpec`, `IdKind`,
  `DEFAULT_IRIS`, `AccessRules.with_iris`. With no policy, IRIs are minted as before.
- **Waiting helpers** (`testkit-wait-until`, #24): `wait_until` and the new `wait_until_async` are
  exported from `rdf_persistence.testkit`.

- **Sweep of a live tenant** (`live-tenant-sweep`): `kit.sweep_tenant(tenant, remove=False,
  remove_blobs=False, older_than=1 hour)` finds the loaded graphs no commit owns and the blobs no
  `file_key` names, older than the grace period, and returns a `TenantSweepReport`. It is a dry run
  by default; `remove` deletes the graphs and `remove_blobs` the blobs (pass it only when every blob
  key is stored in `file_key`). `Session.load_graph` now writes a load marker (`rp:loadedAt`) in the
  registry graph; a graph loaded before the upgrade has none and counts as old, so do not sweep with
  removal during a deploy. Exported: `sweep_tenant`, `TenantSweepReport`, `BlobEntry`, `PendingLoad`.
- **`remove_with_files`**: `kit.remove_with_files(tenant, principal, iri, if_version)` removes a file
  aggregate and the blobs only it names; a failed blob delete is logged and left to the sweep.
  `Session.named_file_keys(keys)` reads which keys a graph still names.

### Changed
- **The boundary REFERENCE problem names its fixes** (`boundary-owned-hint`, #72): annotate the
  slot `owned: true`, make the range an aggregate root, or point the slot at a root, `Principal`
  or `Activity`. Rule id unchanged; the old text stays a prefix.
- **BREAKING for third-party adapters: `FileStore.list_blobs(bucket)`**: the `FileStore` protocol
  gained `list_blobs`, returning `BlobEntry` (`file_key`, `modified`) in key order. Adapter authors
  add it; the `file_store_conformance` suite has a case for it. `FakeFileStore` takes a `clock` to
  stamp `modified`.
- **BREAKING: `TokenVerifier.iris`** (`iri-policy`): a token verifier exposes the `Iris` it mints
  principals with, and `install_service` refuses a verifier whose principal template differs from
  the settings'. `JwksTokenVerifier` takes `iris=Iris(settings)`.
- **Freshness hint** (`generation-fix-hint`, #25): a failed freshness check now names
  `rp-generate`, or the `regenerate-command` of each stale `[tool.rp-generate]` entry, instead of
  `make generate`. A configuration error no longer prints a hint.
- **Releases** (`release-pipeline`): releases are proposed by release-please; `VERSION` removed,
  the version lives in `pyproject.toml`.

## [0.1.0] - 2026-11-06

The first version: the toolkit of change `toolkit-v1-foundation`, archived in
`openspec/changes/archive/2026-11-06-toolkit-v1-foundation/`. Its requirements are the `rp-*`
capabilities in `openspec/specs/`.

### Added
- **Metamodel** in LinkML (`rdf_persistence/model/`): aggregate roots, owned parts, provenance,
  tenancy, ODRL-based access (grants, prohibitions, role definitions) and stored files.
- **Generation** (`rp-generate`). It generates Pydantic classes, SHACL shapes, the JSON-LD context
  and frames, TypeScript types, JSON Schema, OpenAPI components and diagrams from a consumer's
  LinkML schemas. It adds:
  - generator extensions, each with its own test;
  - hard and boundary checks;
  - a manifest with `rp-generate --check`, a freshness pytest plugin and a pre-commit hook.
- **Aggregate store**:
  - sessions and a unit of work over a SPARQL store, with optimistic concurrency, skolemised
    parts, loaded graphs and provenance;
  - the Fuseki adapter.
- **Tenancy**: a database and a bucket per tenant, access records, creation and deletion steps, and
  a start-up sweep.
- **File store**: the `FileStore` port and the S3 adapter (Garage-tested).
- **Identity and tokens**: JWKS token verification and the Zitadel identity adapter.
- **Access check**:
  - per tenant and per aggregate, in a fixed order (scope, state, prohibition, permission,
    action);
  - prohibitions and global roles.
- **Service kit** (`install_service`, `ServiceKit`):
  - a generic router per aggregate root, with JSON, JSON-LD and Turtle by content negotiation;
  - strict bodies with size limits, ETags and `If-Match`, and problem responses;
  - listings with paging, filters and sorting, and an OpenAPI document.
- **Testkit**:
  - fakes of every port;
  - conformance suites for the store, the file store and identity, and a round trip with
    Hypothesis;
  - model and file guards, token signing, and containers for Fuseki, Garage and Zitadel.
- **Docs**: the build guide, the architecture pages, the common questions, and the developer guide
  with the check timings.

<!-- Release process: docs/modules/ROOT/pages/develop/index.adoc#release -->

[Unreleased]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.15.0...HEAD
[0.15.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.8.1...v0.9.0
[0.8.1]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/meaningfy-ws/rdf-persistence/releases/tag/v0.1.0
