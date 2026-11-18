"""Deprecated: this module moved to ``rdf_persistence.persistence.adapters.fuseki``.

``FusekiStore`` is the same class; the old path keeps working, through the re-exports here, until the
shim is removed in the minor release after the one that ships the thematic layout (thematic-structure
PD-8, PD-13). The SPARQL protocol names now live in ``rdf_persistence.persistence.adapters.sparql_protocol``.
"""

import warnings

from rdf_persistence.persistence.adapters.fuseki import (
    ADMIN_DATASETS,
    DATA_ENDPOINT,
    DATASET_TYPE,
    FORM_DB_NAME,
    FORM_DB_TYPE,
    QUERY_ENDPOINT,
    UPDATE_ENDPOINT,
    FusekiStore,
)
from rdf_persistence.persistence.adapters.sparql_protocol import (
    GRAPH_PARAM,
    RESULTS_JSON,
    SPARQL_QUERY,
    SPARQL_UPDATE,
)

warnings.warn(
    "rdf_persistence.adapters.fuseki moved to rdf_persistence.persistence.adapters.fuseki; "
    "the old path will be removed in the minor release after the one that ships the move",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "ADMIN_DATASETS",
    "DATASET_TYPE",
    "DATA_ENDPOINT",
    "FORM_DB_NAME",
    "FORM_DB_TYPE",
    "GRAPH_PARAM",
    "QUERY_ENDPOINT",
    "RESULTS_JSON",
    "SPARQL_QUERY",
    "SPARQL_UPDATE",
    "UPDATE_ENDPOINT",
    "FusekiStore",
]
