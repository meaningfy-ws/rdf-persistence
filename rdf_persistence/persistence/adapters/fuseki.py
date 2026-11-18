"""The Apache Jena Fuseki implementation of the ``Store`` port."""

from http import HTTPMethod
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from rdf_persistence.core.domain.exceptions import NotFound, StoreUnavailable
from rdf_persistence.core.domain.media import ACCEPT, CONTENT_TYPE, N_QUADS
from rdf_persistence.core.services.generated.rp_core_services import HttpSettings
from rdf_persistence.persistence.adapters.generated.rp_persistence_adapters import (
    FusekiDatasetList,
)
from rdf_persistence.persistence.adapters.sparql_protocol import SparqlProtocolStore

# The endpoints of a dataset, and the administration endpoint of Fuseki.
QUERY_ENDPOINT, UPDATE_ENDPOINT, DATA_ENDPOINT = "query", "update", "data"
ADMIN_DATASETS = "/$/datasets"
# The form fields that create a dataset.
FORM_DB_NAME, FORM_DB_TYPE, DATASET_TYPE = "dbName", "dbType", "tdb2"


def _dataset_path(name: str, endpoint: str) -> str:
    return f"/{quote(name, safe='')}/{endpoint}"


class FusekiStore(SparqlProtocolStore):
    """A ``Store`` over Fuseki's SPARQL, Graph Store and admin endpoints, with basic auth."""

    service = "Fuseki"
    unavailable = StoreUnavailable
    db_system_name = "fuseki"

    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        http: HttpSettings | None = None,
    ) -> None:
        super().__init__(
            base_url=url, auth=httpx.BasicAuth(user, password), transport=transport, http=http
        )

    def query_path(self, dataset: str) -> str:
        return _dataset_path(dataset, QUERY_ENDPOINT)

    def update_path(self, dataset: str) -> str:
        return _dataset_path(dataset, UPDATE_ENDPOINT)

    def graph_store_path(self, dataset: str) -> str:
        return _dataset_path(dataset, DATA_ENDPOINT)

    async def export_quads(self, dataset: str) -> bytes:
        response = await self._send(
            HTTPMethod.GET, self.graph_store_path(dataset), headers={ACCEPT: N_QUADS}
        )
        return response.content

    async def import_quads(self, dataset: str, nquads: bytes) -> None:
        await self._send(
            HTTPMethod.POST,
            self.graph_store_path(dataset),
            content=nquads,
            headers={CONTENT_TYPE: N_QUADS},
        )

    async def create_dataset(self, name: str) -> None:
        await self._send(
            HTTPMethod.POST,
            ADMIN_DATASETS,
            data={FORM_DB_NAME: name, FORM_DB_TYPE: DATASET_TYPE},
            on_missing=NotFound,
        )

    async def drop_dataset(self, name: str) -> None:
        await self._send(
            HTTPMethod.DELETE, f"{ADMIN_DATASETS}/{quote(name, safe='')}", on_missing=NotFound
        )

    async def list_datasets(self) -> list[str]:
        response = await self._send(HTTPMethod.GET, ADMIN_DATASETS, on_missing=NotFound)
        try:
            listing = FusekiDatasetList.model_validate_json(response.content)
        except ValidationError as error:
            raise StoreUnavailable(self.unreadable) from error
        return [entry.fuseki_dataset_name.lstrip("/") for entry in listing.datasets]
