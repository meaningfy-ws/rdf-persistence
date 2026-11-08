"""In-memory fakes of the toolkit's ports, for unit tests that must not touch the network."""

from collections import defaultdict
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import ClassVar

from pyparsing import ParseException
from rdflib import Dataset, Graph, URIRef
from rdflib.plugins.sparql import prepareQuery, prepareUpdate
from rdflib.query import Result

from rdf_persistence.domain.exceptions import (
    BadQuery,
    Conflict,
    DatabaseGone,
    NotFound,
    PersistenceError,
    TenantGone,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.service.rp_service import AccountSummary
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.session import Clock, Session, open_session, utc_now

FAKE_DATABASE = "fake"
FAKE_TENANT = "https://example.org/tenants/fake"
FAKE_PRINCIPAL = Principal(id="https://example.org/people/fake")


class _Instrumented:
    """Failure injection and call recording, shared by the fakes.

    ``on(operation, error, times, after)`` makes ``times`` calls of ``operation`` raise ``error``,
    starting ``after`` calls from now; ``sent(operation)`` lists what each call was given, including
    the calls that failed. A name that is not in ``OPERATIONS`` raises ``ValueError``, so a typo
    cannot silently inject nothing.
    """

    OPERATIONS: ClassVar[frozenset[str]] = frozenset()

    def __init__(self) -> None:
        self._failures: defaultdict[str, dict[int, PersistenceError]] = defaultdict(dict)
        self._sent: defaultdict[str, list[str]] = defaultdict(list)

    def on(self, operation: str, error: PersistenceError, times: int = 1, after: int = 0) -> None:
        """Raise ``error`` on ``times`` calls of ``operation``, the first one ``after`` calls from now."""
        self._known(operation)
        first = len(self._sent[operation]) + after
        self._failures[operation].update({first + n: error for n in range(times)})

    def sent(self, operation: str) -> list[str]:
        """What each call of ``operation`` was given, in order."""
        self._known(operation)
        return list(self._sent[operation])

    def _known(self, operation: str) -> None:
        if operation not in self.OPERATIONS:
            raise ValueError(f"unknown operation {operation!r}; known: {sorted(self.OPERATIONS)}")

    def _enter(self, operation: str, payload: str) -> None:
        call = len(self._sent[operation])
        self._sent[operation].append(payload)
        if call in self._failures[operation]:
            raise self._failures[operation].pop(call)


class FakeStore(_Instrumented):
    """A ``Store`` over one rdflib ``Dataset`` per dataset name, with failure injection."""

    OPERATIONS = frozenset(
        {"query", "update", "put_graph", "create_dataset", "drop_dataset", "list_datasets"}
    )

    def __init__(self) -> None:
        super().__init__()
        self._datasets: dict[str, Dataset] = {}

    def _dataset(self, name: str) -> Dataset:
        if name not in self._datasets:
            raise DatabaseGone(f"no dataset {name}")
        return self._datasets[name]

    async def query(self, dataset: str, sparql: str) -> Result:
        self._enter("query", sparql)
        data = self._dataset(dataset)
        try:
            return data.query(prepareQuery(sparql))
        except ParseException as error:
            raise BadQuery(str(error)) from error

    async def update(self, dataset: str, sparql: str) -> None:
        self._enter("update", sparql)
        data = self._dataset(dataset)
        try:
            data.update(prepareUpdate(sparql))
        except ParseException as error:
            raise BadQuery(str(error)) from error

    async def put_graph(self, dataset: str, graph_iri: URIRef, graph: Graph) -> None:
        self._enter("put_graph", str(graph_iri))
        target = self._dataset(dataset).graph(graph_iri)
        target.remove((None, None, None))
        for triple in graph:
            target.add(triple)

    async def create_dataset(self, name: str) -> None:
        self._enter("create_dataset", name)
        if name in self._datasets:
            raise Conflict(f"dataset {name} exists")
        self._datasets[name] = Dataset()

    async def drop_dataset(self, name: str) -> None:
        self._enter("drop_dataset", name)
        if name not in self._datasets:
            raise NotFound(f"no dataset {name}")
        del self._datasets[name]

    async def list_datasets(self) -> list[str]:
        self._enter("list_datasets", "")
        return list(self._datasets)


class FakeFileStore(_Instrumented):
    """A ``FileStore`` in memory, with the same failure injection as ``FakeStore``."""

    OPERATIONS = frozenset(
        {"create_bucket", "delete_bucket", "list_buckets", "put", "get", "delete"}
    )

    def __init__(self) -> None:
        super().__init__()
        self._buckets: dict[str, dict[str, bytes]] = {}

    def _bucket(self, name: str) -> dict[str, bytes]:
        if name not in self._buckets:
            raise TenantGone(f"no bucket {name}")
        return self._buckets[name]

    async def create_bucket(self, name: str) -> None:
        self._enter("create_bucket", name)
        if name in self._buckets:
            raise Conflict(f"bucket {name} exists")
        self._buckets[name] = {}

    async def delete_bucket(self, name: str) -> None:
        self._enter("delete_bucket", name)
        if name not in self._buckets:
            raise NotFound(f"no bucket {name}")
        del self._buckets[name]

    async def list_buckets(self, prefix: str) -> list[str]:
        self._enter("list_buckets", prefix)
        return sorted(name for name in self._buckets if name.startswith(prefix))

    async def put(self, bucket: str, key: str, data: bytes) -> None:
        self._enter("put", f"{bucket}/{key}")
        self._bucket(bucket)[key] = data

    async def get(self, bucket: str, key: str) -> bytes:
        self._enter("get", f"{bucket}/{key}")
        blobs = self._bucket(bucket)
        if key not in blobs:
            raise NotFound(f"no blob {key} in {bucket}")
        return blobs[key]

    async def delete(self, bucket: str, key: str) -> None:
        self._enter("delete", f"{bucket}/{key}")
        self._bucket(bucket).pop(key, None)


class FakeIdentity(_Instrumented):
    """An ``Identity`` over accounts in memory, with the same failure injection as ``FakeStore``.

    It keeps its own copy of each account, and hands out copies. Its accounts are those of one
    organisation: any other id is ``NotFound``, as Zitadel answers for an account of another
    organisation. Given ``roles``, it knows only those, as a project does: granting another is
    ``NotFound``. Without them, it accepts any role. An account whose last role is removed has none
    (``None``), as Zitadel reports it. The ``identity_conformance`` suite pins this.
    """

    OPERATIONS = frozenset(
        {
            "find_by_email",
            "list_accounts",
            "disable",
            "enable",
            "grant_global_role",
            "remove_global_role",
        }
    )

    def __init__(
        self, accounts: Iterable[AccountSummary] = (), *, roles: Iterable[str] | None = None
    ) -> None:
        super().__init__()
        self._roles = None if roles is None else frozenset(roles)
        self._accounts = {a.account_id: a.model_copy(deep=True) for a in accounts}

    def _account(self, account_id: str) -> AccountSummary:
        if account_id not in self._accounts:
            raise NotFound("no such account")
        return self._accounts[account_id]

    async def find_by_email(self, email: str) -> AccountSummary:
        self._enter("find_by_email", email)
        for account in self._accounts.values():
            if account.email == email:
                return account.model_copy(deep=True)
        raise NotFound("no account with that email")

    async def list_accounts(self) -> list[AccountSummary]:
        self._enter("list_accounts", "")
        return [a.model_copy(deep=True) for a in self._accounts.values()]

    async def disable(self, account_id: str) -> None:
        self._enter("disable", account_id)
        self._account(account_id).active = False

    async def enable(self, account_id: str) -> None:
        self._enter("enable", account_id)
        self._account(account_id).active = True

    async def grant_global_role(self, account_id: str, role: str) -> None:
        self._enter("grant_global_role", f"{account_id} {role}")
        account = self._account(account_id)
        if self._roles is not None and role not in self._roles:
            raise NotFound("the project has no such role")
        roles = account.global_roles or []
        if role not in roles:
            account.global_roles = [*roles, role]

    async def remove_global_role(self, account_id: str, role: str) -> None:
        self._enter("remove_global_role", f"{account_id} {role}")
        account = self._account(account_id)
        if account.global_roles:
            account.global_roles = [r for r in account.global_roles if r != role] or None


@asynccontextmanager
async def fake_session(
    store: FakeStore | None = None,
    *,
    tenant_iri: str = FAKE_TENANT,
    principal: Principal = FAKE_PRINCIPAL,
    clock: Clock = utc_now,
    iris: Iris | None = None,
) -> AsyncIterator[Session]:
    """A real ``Session`` over a ``FakeStore``, for unit tests of domain services.

    Pass the same ``store`` to several sessions to share their data; the tenant database is created
    on the store if it is not there yet. ``iris`` is the IRI policy of the code under test (default: the
    default policy).
    """
    store = store or FakeStore()
    if FAKE_DATABASE not in await store.list_datasets():
        await store.create_dataset(FAKE_DATABASE)
    async with open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=tenant_iri,
        principal=principal,
        clock=clock,
        iris=iris,
    ) as session:
        yield session
