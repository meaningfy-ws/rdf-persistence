# Equivalent mutants

The mutants `make mutation` leaves alive, each with why no test should kill it (test-debt-paydown
PD-12). The selection is `setup.cfg [mutmut]` (mutmut 3.8.1); after stage 3 it leaves exactly the 32
below. A survivor that is not in this file is a gap to close or to add here with its reason.

## No legal input tells them apart

- `rdf_persistence.iris.services.iris.x_draw_id__mutmut_10`: `spec.length or 1` differs from
  `or 0` only for a random id with no length, which `check_iri_policy` refuses before any id is drawn.
- `rdf_persistence.iris.services.iris.xǁIrisǁ_probe_types__mutmut_6`: the probe type `""` is used
  only when the template has no `{type}`, and such a template ignores the type it is given.
- `rdf_persistence.iris.services.iris.xǁIrisǁprincipal__mutmut_17`: `quote(sub, safe="XXXX")` only
  adds `X` to the characters left unquoted, and letters are never quoted.

## Only an error message's wording changes (DEC-3)

An error message's wording is not behaviour a caller relies on: no code branches on it, and the
values a refusal must name are asserted where they are read. Each mutant below replaces a message,
or a type name inside it, with other text or with `None`.

- `rdf_persistence.iris.domain.layout.x_root_of_graph__mutmut_11`
- `rdf_persistence.core.domain.exceptions.xǁMessageLimitExceededǁ__init____mutmut_6`: the suffix
  when no message is named
- `rdf_persistence.core.domain.sparql.x__literal__mutmut_6`
- `rdf_persistence.core.domain.sparql.x_term__mutmut_10`
- `rdf_persistence.core.domain.sparql.x_term__mutmut_13`
- `rdf_persistence.core.domain.sparql.x__joined__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_join__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_join__mutmut_8`
- `rdf_persistence.core.domain.sparql.x_join__mutmut_9`
- `rdf_persistence.core.domain.sparql.x_union__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_union__mutmut_9`
- `rdf_persistence.core.domain.sparql.x_union__mutmut_10`
- `rdf_persistence.core.domain.sparql.x_match_patterns__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_contains_patterns__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_contains_patterns__mutmut_7`
- `rdf_persistence.core.domain.sparql.x_contains_patterns__mutmut_8`
- `rdf_persistence.core.domain.sparql.x_value_patterns__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_absent_patterns__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_optional_value_patterns__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_count__mutmut_6`
- `rdf_persistence.core.domain.sparql.x_order_by__mutmut_3`
- `rdf_persistence.core.domain.sparql.x_checked_group__mutmut_3`: the refusal reason, which
  `migrations.py` only copies into its own message
- `rdf_persistence.core.domain.sparql.x_checked_group__mutmut_25`: as above
- `rdf_persistence.core.domain.sparql.x__parsed__mutmut_5`: as above
- `rdf_persistence.core.domain.sparql.x__any_node_problem__mutmut_2`: as above
- `rdf_persistence.core.domain.sparql.x__any_node_problem__mutmut_6`: as above
- `rdf_persistence.core.domain.sparql.x__any_node_problem__mutmut_7`: as above
- `rdf_persistence.core.domain.sparql.x__template_node_problem__mutmut_3`: as above
- `rdf_persistence.tenancy.services.tenant_move.x_check_graphs__mutmut_11`
