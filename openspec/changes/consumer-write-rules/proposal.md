<!-- Parents: issues #415, #397, #387, #386 (filed by MWB2); rp-service-api "A consumer enforces its
     own rules on the writes of any root" and "A consumer rule reads an aggregate its root
     references"; rp-generation "The metamodel declares where its generated classes are imported
     from"; rp-testkit "Consumers test without servers". -->

# EPIC: a consumer's write rules refuse in its own terms, find what they clash with, and are typed and testable

**Golden-thread parents:** issues #415, #397, #387 and #386, filed by MWB2 (v2-04 F-2, v2-06
D-11, v2-07 D-2); `rp-service-api` requirements "A consumer enforces its own rules on the writes of
any root" and "A consumer rule reads an aggregate its root references"; `rp-generation`
"The metamodel declares where its generated classes are imported from"; `rp-testkit` "Consumers
test without servers". Serves the consumer's need (D-12): rules on the generic routes that refuse
with the consumer's own problem, name the aggregate a write clashes with, need no `cast`, and are
unit-tested with a toolkit fake instead of a local stub. Developer's answers: `inputs/qa.md`.

## Appetite

**MEDIUM**, two stages. One capability, the consumer's write rules, deepened: its refusal, its
reader and its registration, with the generation and the OpenAPI changes the refusal needs, one
testkit fake and its conformance kit. Neighbours touched lightly: the importmap gains keys, the
problem handler gains one branch.

## Why

A consumer's write rule can refuse only with the toolkit's generic 422 `invalid-body`, and anything
else it raises becomes a 500. It cannot ask which aggregate already holds a value, so it cannot name
what a write clashes with, and it cannot declare its own problem shape, because a consumer schema
cannot import `Problem` (#415). The only way around is to replace the generic routes with the
consumer's own, which defeats the generic API (#397). Writing the rule needs a `cast` to the
generated class and hand-cutting a workflow state's IRI (#387), and testing it needs a local reader
stub kept in line with the protocol by hand (#386). MWB2 ships without the requirements these
block and records them as deviations and skipped tests.

## Solution outline

- **A consumer declares its own problems.** A consumer's technical schema imports the toolkit's
  technical modules by the same path form as the metamodel modules, and declares a class `is_a:
  Problem` with its own slots. Generation gives a Pydantic class that inherits `Problem` and a
  TypeScript interface that is a `Problem`.
- **A rule refuses with one.** A write rule raises a refusal carrying an instance of such a class;
  the write is refused before anything is written, and the HTTP answer is that problem, its status,
  type, detail and extra fields. The service is told the consumer's problem classes at install, so
  the published OpenAPI of the generic writes lists them and the contract holds.
- **A rule finds what it clashes with.** The reader a rule receives can find the aggregates of a
  class with given slot values, within the write's tenant and only those the writer may read.
- **A rule is typed and testable.** A rule registered for a generated class receives that class.
  The testkit offers a fake reader that records the calls, and one conformance kit holds the fake
  and the real reader to the same contract. A workflow state IRI turns back into its name through a
  public function.

## Key decisions

- **DEC-1:** every schema module under `rdf_persistence/model/technical/**` is importable by a
  consumer schema as `rdf_persistence/model/technical/<theme>/<module>`, as the metamodel modules
  are as `rdf_persistence/model/<module>`. Reason: the issue's path works as written, and one rule
  covers every technical module. Rejected: a new public problem module (a second home for `Problem`);
  only the problem module (a special case in the importmap).
- **DEC-2:** the docs name `Problem` as the only supported extension point among the technical
  modules; the others are importable, not promised stable. A consumer class may extend only a toolkit
  class `rdf_persistence` exports, so generated consumer code keeps importing from the public
  package. Reason: the public surface stays what `__all__` says. Rejected: promising every technical
  class.
- **DEC-3:** a consumer `Problem` subclass lives in a consumer technical module (the boundary rule
  already forbids a domain or value module to import a technical one); its generated Pydantic class
  inherits `Problem`, and its TypeScript interface holds every `Problem` field, so it is assignable
  to `Problem`. Reason: the developer's answer (2026-11-27). Rejected: a hand-written problem class.
- **DEC-4:** a write rule refuses with a consumer problem by raising a refusal that carries an
  instance of a registered `Problem` subclass; the generic create and replace routes answer that
  problem with its extra fields, status 409 or 422. Delete rules keep `Refused`. Reason: #397's
  first expectation, the developer's answer. Rejected: extending `Refused`, which is a `Conflict`
  (code that catches `Conflict` would take a 422 for a version race); any status (a rule answering
  401, 403 or 404 would speak for the access check).
- **DEC-5:** the reader gains `find(cls, **equals)`: the IRIs of the tenant's aggregates of `cls`
  with those slot values, the writer may read and the transaction has not removed or changed
  earlier; `None` is refused; a diagnosis, not a lock. Reason: #397's second expectation. Rejected: a find that relies on versions (a commit
  guard on every match), since uniqueness is the unique keys' job.
- **DEC-6:** rules are registered per generated class through a typed helper, so a rule receives
  that class as its new value with no `cast`; a plain mapping keeps working. `state_name(workflow, iri)`, the inverse
  of `state_iri`, is public. Reason: #387, the developer's answer.
- **DEC-7:** the testkit offers `FakeAggregateReader` and a reader conformance kit that runs one
  contract against it and against the real reader. Reason: #386.
- **DEC-8:** **BREAKING** for a consumer's own `AggregateReader` implementations (a test stub): the
  protocol gains `find`. Flagged in the commit and the CHANGELOG, with the fake as the migration.

## Rabbit-holes

- **The importmap is a CRITICAL blast radius** (GitNexus, 81 dependants): only keys are added; the
  existing keys and their values stay byte-for-byte (RISK-1).
- **The published contract.** `Problem`'s component is closed, so an undocumented problem breaks a
  client that validates answers. The registered classes go into the document; an unregistered one
  is never sent (RISK-3).
- **`find` and the transaction.** It reads the store, so it does not see a root collected earlier in
  the same transaction, and a concurrent write can slip past it. Said in its docstring; the unique
  keys remain the guard.
- **TypeScript `extends`.** The template never writes it, by design; the developer's "extends" is
  met by assignability, checked by `tsc`.

## No-gos

- Consumer problems on delete rules (they keep `Refused`), on tenant writes, grant or root
  validators, or on routes the consumer writes itself.
- A status other than 409 or 422 for a consumer problem.
- A second home for `Problem`, or promising any other technical class as an extension point.
- A `find` that sees uncommitted roots of the same transaction, or guards a version.
- `extends` in the generated TypeScript.
- #402, #417, #414, #410 and any other issue.
- Any consumer term in the package, the tests or the architecture pages.

---

## What Changes

- `rdf_persistence/schema/services/schema.py`: `metamodel_importmap` also maps every
  `model/technical/**` module.
- The generator: a consumer class extending a toolkit technical class imports it from
  `rdf_persistence`; one extending a class `rdf_persistence` does not export fails generation.
- `rdf_persistence/core/domain/exceptions.py`: a `RuleRefusal` error carrying a problem.
- `collaboration/services/aggregate_validators.py`: write rules may raise it; the reader gains
  `find`; typed registration helpers.
- `api/entrypoints/problems.py`, `openapi.py`, `service.py`, `kit.py`: the refusal's answer, the
  registered problem classes and their place in the document.
- `collaboration/services/workflows.py`: `state_name`.
- `testkit/fakes.py`, a new `testkit/reader_conformance.py`.
- The toy library: a technical problem module, a rule that names a key's holder.
- Docs: the validators how-to, `architecture/api.adoc`, the testkit page, `CHANGELOG.md`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-service-api`: the consumer's refusal problem, `reader.find`, typed registration, `state_name`.
- `rp-generation`: technical modules importable by a consumer; extending a toolkit technical class.
- `rp-testkit`: the fake reader and its conformance kit.

## Impact

- `rdf_persistence` gains public names: `RuleRefusal`, `aggregate_rules`, `delete_rules`,
  `state_name`; `rdf_persistence.testkit` gains `FakeAggregateReader`, and the module
  `rdf_persistence.testkit.reader_conformance` holds the contract's cases, as
  `store_conformance` does for stores.
- `install_service` and `ServiceKit` gain `refusal_problems`.
- The OpenAPI document of a service with registered problems changes; one without is unchanged.
