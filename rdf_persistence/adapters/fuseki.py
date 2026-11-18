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

# Names of the module before the split (PD-8: its other names); the store now builds its messages from
# its ``service``, with the same text for Fuseki.
BAD_QUERY_MESSAGE = "Fuseki refused the SPARQL text as malformed"
UNREADABLE = "Fuseki answered with something unreadable"

warnings.warn(
    "rdf_persistence.adapters.fuseki moved to rdf_persistence.persistence.adapters.fuseki; "
    "the old path will be removed in the minor release after the one that ships the move",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "ADMIN_DATASETS",
    "BAD_QUERY_MESSAGE",
    "DATASET_TYPE",
    "DATA_ENDPOINT",
    "FORM_DB_NAME",
    "FORM_DB_TYPE",
    "GRAPH_PARAM",
    "QUERY_ENDPOINT",
    "RESULTS_JSON",
    "SPARQL_QUERY",
    "SPARQL_UPDATE",
    "UNREADABLE",
    "UPDATE_ENDPOINT",
    "FusekiStore",
]
