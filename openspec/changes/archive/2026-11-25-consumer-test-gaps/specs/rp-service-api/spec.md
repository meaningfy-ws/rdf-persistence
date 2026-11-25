## ADDED Requirements

### Requirement: A referrer says where to read it

Each referrer in the `in-use` problem and in the referrers listing SHALL carry `referrer_rp_path`
and `referrer_id` when its class is a served aggregate root and its IRI matches the IRI policy's
aggregate template, and SHALL carry neither otherwise.

#### Scenario: the client follows a referrer
- **GIVEN** an aggregate of a served class that refers to a root
- **WHEN** the root's delete is refused with 409 `in-use`, or its referrers are listed
- **THEN** each named referrer carries `referrer_rp_path` and `referrer_id`, and `GET {tenant_segment}/{t}/{referrer_rp_path}/{referrer_id}` returns that referrer

#### Scenario: a referrer that cannot be located
- **GIVEN** a referrer row whose class is not a served root, or whose IRI does not match the aggregate template
- **WHEN** it is named in the problem or the listing
- **THEN** it carries neither field, and its other members are unchanged

#### Scenario: an unfiltered refusal still names nobody
- **GIVEN** an `InUse` error that no `readable` callable judged
- **WHEN** it is answered
- **THEN** `referrers` is empty and every referrer is counted in `hidden_count`
