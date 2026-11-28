## MODIFIED Requirements

### Requirement: A consumer rule refuses a write with its own problem

`install_service` and `ServiceKit` SHALL take optional `refusal_problems`, generated classes that
extend `Problem`; start-up SHALL refuse one that does not, naming it. A write rule SHALL be able to
raise `RuleRefusal(problem)` with an instance of a registered class whose status is 409 or 422. The
write SHALL then be refused before anything is written, and the generic create and replace routes
SHALL answer with that problem: its status, type, title, detail and every extra field. A refusal
whose problem is not of a registered class, or whose status is neither 409 nor 422, SHALL be
answered as the 500 internal-error problem and logged once, naming the rule's problem class,
with the refusal's traceback, which names the rule (D-22); a refusal that is answered SHALL NOT
be logged as an error. In-process,
the commit SHALL raise the `RuleRefusal`.
The OpenAPI document SHALL list each registered class as a component schema, and the 409 and 422
answers of the generic create and replace routes and every operation's `default` answer SHALL
accept it beside their problem schema; start-up SHALL refuse a registered class whose name is
already a component, naming it. With no registered class the document SHALL be unchanged.

#### Scenario: a refusal with a consumer problem type
- **GIVEN** a registered problem class `HeldKeyProblem` with an extra slot `holder`, and a write rule for `Book` that raises `RuleRefusal(HeldKeyProblem(type=T, title="Key held", status=409, detail=d, holder=h))`
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is 409 with problem type `T`, detail `d` and `holder` `h`, and nothing is written

#### Scenario: a 422 refusal
- **GIVEN** the same class and a rule that refuses with status 422 and problem type `T`
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is 422 with problem type `T` and the rule's detail

#### Scenario: an unregistered problem class
- **GIVEN** a rule that raises `RuleRefusal` with an instance of a `Problem` subclass not in `refusal_problems`
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is the 500 internal-error problem, with none of the rule's fields, and the log names the class

#### Scenario: a status outside 409 and 422
- **GIVEN** a rule that refuses with a registered class and status 403
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is the 500 internal-error problem, and nothing is written

#### Scenario: a class that is not a problem
- **GIVEN** `refusal_problems` naming a class that does not extend `Problem`
- **WHEN** the service starts
- **THEN** it refuses to start, naming the class

#### Scenario: the document lists the problem
- **GIVEN** the registered problem class `HeldKeyProblem`
- **WHEN** a client reads `/openapi.json`
- **THEN** `HeldKeyProblem` is a component schema with `holder`
- **AND** the 409 and 422 answers of each aggregate's create and replace, and every `default` answer, accept `HeldKeyProblem` or their former problem schema
- **AND** no other answer changes

#### Scenario: a registered name that is already a component
- **GIVEN** a registered `Problem` subclass named like an aggregate class of the schema
- **WHEN** the service starts
- **THEN** it refuses to start, naming the class
