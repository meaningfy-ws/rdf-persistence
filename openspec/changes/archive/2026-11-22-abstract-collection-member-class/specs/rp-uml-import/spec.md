## MODIFIED Requirements

### Requirement: The toolkit is reused, not redefined

The converter SHALL map toolkit concepts to the toolkit's own classes, slots and annotations: default
mixins on roots and labelled parts, `rp_mixins` and drawn generalisations to toolkit classes, slots
whose IRI is a toolkit slot's `slot_uri` (except `id`), and every class tagged value named like a
toolkit class annotation. A «tenant root» becomes the class of the tenant's meta graph, not an
aggregate root; an abstract class whose concrete descendants are all roots, and which a slot ranges
over, becomes an aggregate root. A reference collection's `dct:hasPart` role to another converted
class fixes the collection's `member_class` to that class, except on an abstract collection whose
subclass draws its own such role: there only the subclasses fix it, each to a class that descends
from the parent's.

#### Scenario: a reference collection's member class
- **GIVEN** `«root» lib:Shelf` tagged `rp_mixins=ReferenceCollection` (or generalising a class that
  is) with a `dct:hasPart` role to `«root» lib:Book`
- **WHEN** it is converted
- **THEN** `Shelf` has `slot_usage: {member_class: {equals_string: Book}}`, a `Shelf` of another
  member class is refused by its model and its shape, and the report has no `toolkit-slot-kept`
  line for the role; a role to `Shelf` itself (nesting) stays the toolkit's `has_part`, reported as
  before, and roles to two different classes fail the run naming `Shelf`

#### Scenario: an abstract collection narrowed by its subclasses
- **GIVEN** an abstract `lib:Collection` tagged `rp_mixins=ReferenceCollection` with a `dct:hasPart`
  role to an abstract `lib:Resource`, and `«root» lib:Shelf` generalising it with its own
  `dct:hasPart` role to `«root» lib:Book`, which generalises `Resource`
- **WHEN** it is converted and generated
- **THEN** `Shelf` fixes `member_class` to `Book`, `Collection` fixes none and its role is reported
  as `toolkit-slot-kept` with its range, and the generated code passes the type check; when no
  subclass draws its own role, `Collection` keeps `Resource`; a subclass role to a class that does
  not descend from `Resource` fails the run naming `Shelf`, its class, `Collection` and `Resource`

#### Scenario: a root that is an activity
- **GIVEN** `«root» lib:Loan` tagged `rp_mixins=Activity` with `prov:startedAtTime [1..1]` and `rp_path=loans`
- **WHEN** it is converted
- **THEN** `Loan` is `is_a: Activity`, mixes in `AggregateRoot`, `Described` and `Tracked`, has
  `annotations: {rp_path: loans}`, defines no new slot and narrows no toolkit-filled slot (the
  `[1..1]` on `started_at_time` is dropped), and the report names `started_at_time`

#### Scenario: a tagged value becomes an annotation
- **GIVEN** a class tagged `rp_writes=service`
- **WHEN** it is converted
- **THEN** it carries `annotations: {rp_writes: service}`, and a value outside `WritesKind` fails the run

#### Scenario: a business identifier
- **GIVEN** `lib:Book` with `dct:identifier : xsd:string [1..1]`
- **WHEN** it is converted
- **THEN** it has a required string slot `identifier` (`slot_uri: dcterms:identifier`) and keeps `id` as its IRI

#### Scenario: an excluded package
- **GIVEN** `--exclude-package circulation` and an association `lib:Book → circulation:Loan`
- **WHEN** the model is converted
- **THEN** no slot is produced and the report names the association
