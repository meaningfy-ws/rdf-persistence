"""Reads of the metamodel that only tests need (it left ``schema.services.vocabulary``, which no code of the toolkit used it from)."""

from collections.abc import Mapping

from rdflib import URIRef

from rdf_persistence.schema.services.vocabulary import metamodel


def enum_meanings(name: str) -> Mapping[str, URIRef]:
    """The meaning IRI of each permissible value of the metamodel's enum ``name``, by the value's text.

    A generated enum is a ``str`` enum, so a caller looks a member up in the result as it would by its value.
    """
    view = metamodel()
    values = view.get_enum(name).permissible_values
    return {text: URIRef(view.expand_curie(str(value.meaning))) for text, value in values.items()}


TENANT_STATE_IRIS = enum_meanings("TenantState")
