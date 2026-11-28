"""In-memory fakes of the toolkit's ports, for unit tests that must not touch the network."""

import asyncio
import re
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import ClassVar, cast

from pydantic import BaseModel
from pyparsing import ParseException
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.query import Result
from rdflib.term import Node

from rdf_persistence.access.services.generated.rp_access_services import AccountSummary
from rdf_persistence.collaboration.services.aggregate_validators import checked_find_values
from rdf_persistence.core.domain.exceptions import (
    BadQuery,
    Conflict,
    DatabaseGone,
    NotFound,
    PersistenceError,
    TenantGone,
)
from rdf_persistence.core.domain.generated.rp_core import AggregateKey, DependenceLink, Principal
from rdf_persistence.core.domain.media import N_QUADS
from rdf_persistence.core.domain.sparql_parsing import prepare_query, prepare_update
from rdf_persistence.events.services.events import Receive
from rdf_persistence.events.services.generated.rp_events_services import EventEnvelope
from rdf_persistence.files.domain.blob_keys import checked_blob_key
from rdf_persistence.files.domain.generated.rp_files import BlobEntry
from rdf_persistence.iris.services.iris import DEFAULT_IRIS, Iris
from rdf_persistence.persistence.services.generated.rp_persistence_services import Contains
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.referrers import Dependents, RemovalRefusal
from rdf_persistence.persistence.services.session import (
    Clock,
    OnCommit,
    Session,
    WriteGuard,
    open_session,
    utc_now,
)
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity

Message = tuple[EventEnvelope, bytes]

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


# What a ';' inside must not split: an IRI, a string (short or long, with escapes), a comment.
# The branches of a long string are disjoint (a plain character, an escape, or a quote that does not
# start the closing three), so an unterminated one is scanned in linear time.
# shortcut: a splitter of our own for the fake, since rdflib's update parser recurses once per
# operation and fails from about 50 to 100 (rdflib#3710); drop it when a fixed rdflib is pinned.
_OPEN_BRACE, _CLOSE_BRACE, _SEMICOLON = "{", "}", ";"
_SPARQL_TOKENS = re.compile(
    r"""<[^<>"{}|^`\\\s]*>|\"\"\"(?:[^"\\]|\\.|"(?!""))*\"\"\"|'''(?:[^'\\]|\\.|'(?!''))*'''"""
    r"""|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|#[^\n]*|([;{}])""",
    re.DOTALL,
)
_PROLOGUE = re.compile(r"\s*(?:(?:PREFIX\s+[^\s:]*:\s*<[^>]*>|BASE\s*<[^>]*>)\s*)+", re.IGNORECASE)


def _operations(request: str) -> list[str]:
    """The operations of an update request, split at its top-level ``;`` (not one inside braces,
    where it joins predicate lists), empty ones dropped."""
    parts, start, depth = [], 0, 0
    for token in _SPARQL_TOKENS.finditer(request):
        mark = token.group(1)
        depth += (mark == _OPEN_BRACE) - (mark == _CLOSE_BRACE)
        if mark == _SEMICOLON and depth == 0:
            parts.append(request[start : token.start()])
            start = token.end()
    return [part for part in [*parts, request[start:]] if part.strip()]


def _plain_strings(data: Dataset) -> None:
    """Read each ``xsd:string`` literal of ``data`` as the plain literal of its text, as Fuseki does."""
    typed = [q for q in data.quads() if isinstance(q[2], Literal) and q[2].datatype == XSD.string]
    for s, p, o, g in typed:
        graph = data.graph(g)
        graph.remove((s, p, o))
        graph.add((s, p, Literal(str(o))))


class _Hold:
    """The state of one open ``FakeStore.hold``: who waits, how many calls came, whether it is spent."""

    def __init__(self, until: int, timeout: float) -> None:
        self.until = until
        self.timeout = timeout
        self.seen = 0
        self.seen_at_release = (
            0  # the calls that came before the hold was spent: the only ones that fill it
        )
        self.spent = False
        self._waiters: list[asyncio.Future[None]] = []
        self._timer: asyncio.Task[None] | None = None

    async def arrive(self) -> None:
        """Count a call; make it wait for its turn unless the hold is spent."""
        self.seen += 1
        if self.spent:
            return
        mine: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters.append(mine)
        if self.seen >= self.until:
            await self.release()
        elif self._timer is None:
            self._timer = asyncio.create_task(self._expire())
        await mine

    async def release(self) -> None:
        """Resolve the waiters one at a time, in arrival order, each one running before the next."""
        if not self.spent:
            self.seen_at_release = self.seen
        self.spent = True
        if self._timer is not None and self._timer is not asyncio.current_task():
            self._timer.cancel()
        while self._waiters:
            waiter = self._waiters.pop(0)
            if not waiter.done():
                waiter.set_result(None)
            await asyncio.sleep(0)

    async def close(self) -> None:
        await self.release()
        if self._timer is not None:
            await asyncio.wait([self._timer])

    async def _expire(self) -> None:
        await asyncio.sleep(self.timeout)
        await self.release()


class FakeStore(_Instrumented):
    """A ``Store`` over one rdflib ``Dataset`` per dataset name, with failure injection.

    Data that enters the store reads an ``xsd:string`` literal as the plain literal of the same
    text, so a query compares them as Fuseki does (one term).

    ``hold(operation, until, timeout)`` makes the first ``until`` calls of ``operation`` wait for
    each other, then releases them one by one in arrival order: the first arrival applies first, so
    a test can make two writers meet at one version. A call waits before it is recorded in ``sent``
    and before it takes an armed fault. Calls after the ``until``-th do not wait. A hold that has
    not filled ``timeout`` seconds after its first waiter arrived releases its waiters; a call that
    arrives after that release runs at once and does not fill the hold. Leaving the block releases
    any that remain, and raises ``AssertionError`` unless ``until`` calls came before the release
    (an exception that leaves the block is never masked by it). Hold ``update`` only inside
    ``kit.relay.paused()``: the relay's own mark is an ``update``, and it would fill the hold
    (RISK-3 of ``consumer-test-gaps``), so the test would be flaky.

    ``update`` applies a request to a copy of the dataset and keeps the copy only if every operation
    succeeds, so a request is atomic as on Fuseki; any failure is a ``BadQuery``. ``after_update``,
    when set, is awaited after a successful update and before it returns, so a test can make another
    writer act between an update and the caller's next read.
    """

    db_system_name = "rdflib"

    OPERATIONS = frozenset(
        {
            "query",
            "update",
            "put_graph",
            "export_quads",
            "import_quads",
            "create_dataset",
            "drop_dataset",
            "list_datasets",
        }
    )

    def __init__(self) -> None:
        super().__init__()
        self._datasets: dict[str, Dataset] = {}
        self.after_update: Callable[[], Awaitable[None]] | None = None
        self._holds: dict[str, _Hold] = {}

    @asynccontextmanager
    async def hold(self, operation: str, until: int, timeout: float = 5.0) -> AsyncIterator[None]:
        """Make the first ``until`` calls of ``operation`` in the block meet before any applies.

        Raises:
            ValueError: ``operation`` is unknown, or ``until`` is below 1.
            RuntimeError: ``operation`` already has an open hold.
            AssertionError: On a clean exit, fewer than ``until`` calls came before the release
                (a call after the timeout does not count).
        """
        self._known(operation)
        if until < 1:
            raise ValueError(f"until must be at least 1, not {until}")
        if operation in self._holds:
            raise RuntimeError(f"{operation!r} is already held")
        held = self._holds[operation] = _Hold(until, timeout)
        try:
            yield
        finally:
            del self._holds[operation]
            await held.close()
        if held.seen_at_release < until:
            raise AssertionError(
                f"hold({operation!r}, until={until}) saw {held.seen_at_release} call(s)"
            )

    async def _gate(self, operation: str) -> None:
        """The waiting point of a held operation; every async operation awaits it first."""
        held = self._holds.get(operation)
        if held is not None:
            await held.arrive()

    def _dataset(self, name: str) -> Dataset:
        if name not in self._datasets:
            raise DatabaseGone(f"no dataset {name}")
        return self._datasets[name]

    async def query(self, dataset: str, sparql: str) -> Result:
        await self._gate("query")
        self._enter("query", sparql)
        data = self._dataset(dataset)
        try:
            return data.query(prepare_query(sparql))
        except ParseException as error:
            raise BadQuery(str(error)) from error

    async def update(self, dataset: str, sparql: str) -> None:
        await self._gate("update")
        self._enter("update", sparql)
        data = self._dataset(dataset)
        copy = Dataset()
        # rdflib's stubs type the graph of a quad as a Graph in addN, though quads() yields identifiers
        copy.addN(cast(Iterable[tuple[Node, Node, Node, Graph]], data.quads()))
        operations = _operations(sparql)  # our own code: a failure here is not the caller's query
        prologue = ""  # PREFIX and BASE declarations apply to the operations after them
        try:
            for operation in operations:
                copy.update(prepare_update(prologue + operation))
                found = _PROLOGUE.match(operation)
                prologue += found.group() if found else ""
        except RecursionError:
            raise
        except Exception as error:  # rdflib raises a bare Exception at run time (PD-13)
            raise BadQuery(str(error)) from error
        _plain_strings(copy)
        self._datasets[dataset] = copy
        if self.after_update is not None:
            await self.after_update()

    async def put_graph(self, dataset: str, graph_iri: URIRef, graph: Graph) -> None:
        await self._gate("put_graph")
        self._enter("put_graph", str(graph_iri))
        target = self._dataset(dataset).graph(graph_iri)
        target.remove((None, None, None))
        for triple in graph:
            target.add(triple)
        _plain_strings(self._dataset(dataset))

    async def export_quads(self, dataset: str) -> bytes:
        await self._gate("export_quads")
        self._enter("export_quads", dataset)
        return self._dataset(dataset).serialize(format=N_QUADS).encode()

    async def import_quads(self, dataset: str, nquads: bytes) -> None:
        await self._gate("import_quads")
        self._enter("import_quads", dataset)
        self._dataset(dataset).parse(data=nquads, format=N_QUADS)
        _plain_strings(self._dataset(dataset))

    async def create_dataset(self, name: str) -> None:
        await self._gate("create_dataset")
        self._enter("create_dataset", name)
        if name in self._datasets:
            raise Conflict(f"dataset {name} exists")
        self._datasets[name] = Dataset()

    async def drop_dataset(self, name: str) -> None:
        await self._gate("drop_dataset")
        self._enter("drop_dataset", name)
        if name not in self._datasets:
            raise NotFound(f"no dataset {name}")
        del self._datasets[name]

    async def list_datasets(self) -> list[str]:
        await self._gate("list_datasets")
        self._enter("list_datasets", "")
        return list(self._datasets)


class FakeFileStore(_Instrumented):
    """A ``FileStore`` in memory, with the same failure injection as ``FakeStore``."""

    OPERATIONS = frozenset(
        {"create_bucket", "delete_bucket", "list_buckets", "put", "get", "delete", "list_blobs"}
    )

    def __init__(self, clock: Clock = utc_now) -> None:
        super().__init__()
        self._clock = clock
        self._buckets: dict[str, dict[str, bytes]] = {}
        self._modified: dict[tuple[str, str], datetime] = {}

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
        checked_blob_key(key)  # refuses as the S3 adapter does
        self._bucket(bucket)[key] = data
        self._modified[bucket, key] = self._clock()

    async def list_blobs(self, bucket: str) -> list[BlobEntry]:
        self._enter("list_blobs", bucket)
        return [
            BlobEntry(file_key=key, modified=self._modified[bucket, key])
            for key in sorted(self._bucket(bucket))
        ]

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
    iris: Iris = DEFAULT_IRIS,
    listings: Listings | None = None,
    keys: Sequence[AggregateKey] = (),
    guards: WriteGuard | None = None,
    dependents: Dependents = (),
    record_activities: bool = True,
    on_commit: OnCommit | None = None,
    removals: RemovalRefusal | None = None,
    dependence: Sequence[DependenceLink] = (),
    limits: LimitSettings | None = None,
) -> AsyncIterator[Session]:
    """A real ``Session`` over a ``FakeStore``, for unit tests of domain services.

    Pass the same ``store`` to several sessions to share their data; the tenant database is created
    on the store if it is not there yet. ``iris`` is the IRI policy of the code under test (default: the
    default policy). ``keys`` are the keys across aggregates the session enforces (default: none).
    ``record_activities`` and ``on_commit`` are the session's (message-bus PD-9, PD-10).
    ``removals`` are the session's: the classes whose roots it refuses to remove while referenced.
    ``dependence`` and ``limits`` are the session's links of dependence and central limits.
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
        listings=listings,
        keys=keys,
        guards=guards,
        dependents=dependents,
        record_activities=record_activities,
        on_commit=on_commit,
        removals=removals,
        dependence=dependence,
        limits=limits,
    ) as session:
        yield session


class FakeAggregateReader:
    """An ``AggregateReader`` over models seeded by hand, for a rule's unit test.

    ``roots`` are the classes ``find`` accepts, as the real reader accepts only aggregate roots with
    a path; ``unreadable`` are seeded ids the writer may not read, which no method then shows.
    ``calls`` records ``(method, args, kwargs)`` of every call in order, refused calls included.

    ``find`` answers the sorted ids of the readable models of exactly ``cls`` whose slots equal the
    values: on a multivalued slot a single value means "one of the values is it", a list "all its
    items are among them". It refuses what the real reader refuses (``ValueError``, ``TypeError``,
    ``BadQuery``). A ``Contains`` and a dotted keyword are the fake's limit: ``NotImplementedError``.
    ``rdf_persistence.testkit.reader_conformance`` holds it to the real reader.
    """

    def __init__(
        self,
        aggregates: Iterable[BaseModel] = (),
        *,
        roots: Iterable[type[BaseModel]],
        unreadable: Iterable[str] = (),
    ) -> None:
        # a root has an ``id``; ``BaseModel`` does not say so
        self._models = {str(getattr(model, "id")): model for model in aggregates}  # noqa: B009
        self._roots = tuple(roots)
        self._unreadable = frozenset(unreadable)
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _readable(self, iri: str) -> BaseModel | None:
        return None if iri in self._unreadable else self._models.get(iri)

    async def classes_of(self, iri: str) -> frozenset[str]:
        self.calls.append(("classes_of", (iri,), {}))
        model = self._readable(iri)
        return frozenset() if model is None else frozenset({type(model).__name__})

    async def aggregate(self, iri: str) -> BaseModel | None:
        self.calls.append(("aggregate", (iri,), {}))
        model = self._readable(iri)
        return None if model is None else model.model_copy(deep=True)

    async def find(self, cls: type[BaseModel], **equals: object) -> list[str]:
        self.calls.append(("find", (cls,), dict(equals)))
        for slot, value in equals.items():
            if value is None:
                raise TypeError(
                    f"find({cls.__name__}): {slot} is None; a rule asks for a value, never for its absence"
                )
        if cls not in self._roots:
            raise ValueError(f"{cls.__name__} is not an aggregate root with a path")
        wanted = {slot: self._wanted(cls, slot, value) for slot, value in equals.items()}
        return sorted(
            iri
            for iri, model in self._models.items()
            if type(model) is cls
            and iri not in self._unreadable
            and all(self._holds(model, slot, wants) for slot, wants in wanted.items())
        )

    @staticmethod
    def _wanted(cls: type[BaseModel], slot: str, value: object) -> list[object]:
        """The values asked for on ``slot``, each validated against the slot's item type."""
        items = list(value) if isinstance(value, (list, tuple)) else [value]
        if slot.count(".") or any(isinstance(item, Contains) for item in items):
            raise NotImplementedError(
                f"the fake reader does not answer {slot!r} (a Contains or a dotted keyword)"
            )
        if slot not in cls.model_fields:
            raise BadQuery(f"{slot} is not a slot of {cls.__name__}")
        if not items:
            raise ValueError(f"find({cls.__name__}): {slot} is an empty list")
        return checked_find_values(cls, slot, items)

    @staticmethod
    def _holds(model: BaseModel, slot: str, wants: list[object]) -> bool:
        stored = getattr(model, slot)
        have = stored if isinstance(stored, list) else [] if stored is None else [stored]
        return all(want in have for want in wants)


class InMemoryBroker:
    """The broker the in-memory buses share: every message sent, as (envelope, JSON bytes)."""

    def __init__(self) -> None:
        self.messages: list[Message] = []
        self._buses: list[InMemoryEventBus] = []


class InMemoryEventBus:
    """An ``EventBus`` that delivers to every started bus on its broker, itself included.

    A message whose ``receive`` raised stays unacked for that bus and comes again when that bus is
    started again. ``fail_next_publish`` makes the next ``publish`` raise.
    """

    def __init__(self, broker: InMemoryBroker) -> None:
        self._broker = broker
        self._receive: Receive | None = None
        self._unacked: list[Message] = []
        self._fail_next = False

    def fail_next_publish(self) -> None:
        self._fail_next = True

    async def publish(self, envelope: EventEnvelope, body: Activity) -> None:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("the in-memory broker was told to fail")
        message = (envelope, body.model_dump_json(exclude_none=True).encode())
        self._broker.messages.append(message)
        for bus in list(self._broker._buses):
            await bus._deliver(message)

    async def start(self, receive: Receive) -> None:
        self._receive = receive
        if self not in self._broker._buses:
            self._broker._buses.append(self)
        for message in list(self._unacked):
            await self._deliver(message)

    async def close(self) -> None:
        self._receive = None
        if self in self._broker._buses:
            self._broker._buses.remove(self)

    async def _deliver(self, message: Message) -> None:
        assert self._receive is not None
        try:
            await self._receive(*message)
        except Exception:  # noqa: BLE001 -- a failing receiver is a nack, as the real broker treats it
            if message not in self._unacked:
                self._unacked.append(message)
        else:
            if message in self._unacked:
                self._unacked.remove(message)
