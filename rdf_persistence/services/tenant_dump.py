"""Dump a tenant to one archive and restore an archive into a new tenant (tenant-dump-restore).

The archive is a gzipped tar read and written as a stream: ``manifest.json`` (a ``TenantDump``), ``graphs.nq``
(every named graph of the tenant's database), then ``blobs/<key>`` for each blob of its bucket. A restore checks
the manifest and the quads before it creates anything, so a refused dump leaves nothing behind (PD-5); the blobs
are read and stored one at a time after the new database and bucket exist, which ``Tenancy.restore`` cleans up if
anything fails (PD-6). ``rewrite`` and ``glued_templates`` are the pure part: moving the quads to the new tenant id (PD-4).
"""

import gzip
import io
import logging
import re
import tarfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import BinaryIO

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import Dataset, URIRef
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.term import Node

from rdf_persistence.domain.exceptions import Conflict, InvalidBody, InvalidIri, NotFound
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import (
    IriPolicy,
    TenantDump,
    TenantSummary,
)
from rdf_persistence.domain.iris import Iris, policy_differences
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.session import Clock, utc_now
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)

FORMAT_VERSION = 1
MANIFEST, GRAPHS, BLOBS = "manifest.json", "graphs.nq", "blobs/"
NQUADS = "nquads"  # rdflib's name for N-Quads
# What a damaged gzip or tar stream raises while it is read.
_DAMAGED = (tarfile.TarError, gzip.BadGzipFile, EOFError, zlib.error)

# A character that would make the id part of a longer word; the ids of a policy are drawn from [a-z0-9].
_WORD = "[a-z0-9]"
_ID_GLUED_BEFORE = re.compile(rf"(?:{_WORD}|\}})\{{tenant_id\}}")
_ID_GLUED_AFTER = re.compile(rf"\{{tenant(?:_id)?\}}(?:{_WORD}|\{{)")


def rewrite(dataset: Dataset, base: str, old_id: str, new_id: str) -> Dataset:
    """A copy of ``dataset`` whose IRIs under ``base`` carry ``new_id`` where they carried ``old_id``.

    Only the graph name, subject and object of each quad are looked at, and only when they are IRIs that
    start with ``base``. In the text after ``base``, every ``old_id`` that has no ``[a-z0-9]`` character on
    either side (or the IRI's end) is replaced. Predicates, datatypes, literals and blank nodes stay as
    they are. A principal IRI under ``base`` whose subject equals ``old_id`` is rewritten too (RISK-3).
    """
    token = re.compile(rf"(?<!{_WORD}){re.escape(old_id)}(?!{_WORD})")

    def move(term: Node | None) -> Node | None:
        if isinstance(term, URIRef) and term.startswith(base):
            return URIRef(base + token.sub(new_id, term[len(base) :]))
        return term

    result = Dataset()
    for subject, predicate, obj, graph in dataset.quads():
        result.graph(move(graph)).add((move(subject), predicate, move(obj)))  # type: ignore[arg-type]
    return result


def glued_templates(policy: IriPolicy) -> list[str]:
    """The templates of an effective ``policy`` that put the tenant id next to a letter, a digit or a variable.

    Their IRIs cannot be rewritten safely: the id is not delimited. These are the templates where the
    character before ``{tenant_id}``, or after ``{tenant_id}`` or ``{tenant}``, is in ``[a-z0-9]`` or is
    another ``{variable}``. The settings' ``{base}`` must be written in already (``Iris.effective_policy``).
    """
    return [
        name
        for name, template in policy
        if name.endswith("_template")
        and template
        and (_ID_GLUED_BEFORE.search(template) or _ID_GLUED_AFTER.search(template))
    ]


# -- dump (PD-7) ------------------------------------------------------------------------------------


async def dump(
    tenancy: Tenancy,
    store: Store,
    files: FileStore,
    iris: Iris,
    view: SchemaView,
    tenant: str,
    out: BinaryIO,
    *,
    clock: Clock = utc_now,
) -> TenantDump:
    """Write the active tenant ``tenant`` to ``out`` as a dump archive and answer its manifest.

    The tenant's graphs are read once and every blob once, one at a time. A blob listed and gone before its
    read is left out and logged (step ``dump-blob-gone``). Nothing is written to ``out`` before the tenant is
    known to be active and its graphs are read.

    Raises:
        NotFound: The tenant has no access record.
        Conflict: The tenant is being deleted.
    """
    record, _ = await tenancy.get(tenant)
    if record.state == TenantState.DELETING:
        raise Conflict(f"{tenant} is being deleted")
    database = record.database_name
    # shortcut: the N-Quads of the whole tenant are held in memory; stream them once a tenant outgrows memory
    quads = await store.export_quads(database)
    blobs = await files.list_blobs(database)
    stamp = clock()
    manifest = TenantDump(
        format_version=FORMAT_VERSION,
        created_at=stamp,
        toolkit_version=_toolkit_version(),
        schema_id=view.schema.id,
        schema_version=view.schema.version,
        source_tenant=tenant,
        source_tenant_id=iris.tenant_id_of(tenant),
        label=record.label,
        iri_policy=iris.effective_policy,
    )
    with tarfile.open(fileobj=out, mode="w|gz") as tar:
        for name, payload in ((MANIFEST, manifest.model_dump_json().encode()), (GRAPHS, quads)):
            _add(tar, name, payload, stamp.timestamp())
        for blob in blobs:
            try:
                payload = await files.get(database, blob.file_key)
            except NotFound:
                log.warning(
                    "a blob was deleted between listing and reading; left out of the dump",
                    extra={"step": "dump-blob-gone", "tenant": tenant, "resource": blob.file_key},
                )
                continue
            _add(tar, BLOBS + blob.file_key, payload, stamp.timestamp())
    return manifest


def _toolkit_version() -> str:
    """The installed toolkit's version (services may not import the top-level package: it loads the adapters)."""
    try:
        return version("rdf-persistence")
    except PackageNotFoundError:  # run from a source tree that is not installed
        return "unknown"


def _add(tar: tarfile.TarFile, name: str, payload: bytes, mtime: float) -> None:
    member = tarfile.TarInfo(name)
    member.size, member.mtime = len(payload), int(mtime)
    tar.addfile(member, io.BytesIO(payload))


# -- restore (PD-3, PD-5, PD-6) ----------------------------------------------------------------------


async def restore(
    tenancy: Tenancy, iris: Iris, view: SchemaView, src: BinaryIO, creator: Principal
) -> TenantSummary:
    """Create a new tenant out of the dump archive in ``src``; ``creator`` is granted the creator role in it.

    The manifest and the quads are read and checked first and nothing is created if they are refused. The
    blobs are read from the stream and stored one at a time.

    Raises:
        InvalidBody: The archive is not a dump of this service (its layout, format version, schema, IRI policy,
            graphs or root), or a member among the blobs is not a blob.
        PersistenceError: The tenant could not be created; see ``Tenancy.restore``.
    """
    with _opened(src) as (tar, stream):
        members = iter(tar)
        manifest = _manifest(tar, members)
        _check_manifest(manifest, view, iris)
        quads = _read(tar, _member(members, GRAPHS), GRAPHS)
        tenant = await tenancy.free_tenant()
        data = _moved(quads, manifest, tenant, iris)
        _check_graphs(data, tenant, iris)
        label = tenancy.vet_restored_root(tenant, data.graph(iris.meta(tenant)), creator)
        return await tenancy.restore(tenant, data, label, _blobs(tar, members, stream), creator)


@contextmanager
def _opened(src: BinaryIO) -> Iterator[tuple[tarfile.TarFile, gzip.GzipFile]]:
    """The tar and, under it, the gzip stream: that one is read to its end marker (PD-12 F1), which the tar does not reach."""
    stream = gzip.GzipFile(fileobj=src)
    with _readable("it is not a gzipped tar"):
        # a stream: members are read in order, never back; closed by the ``with`` below
        tar = tarfile.open(fileobj=stream, mode="r|")  # noqa: SIM115
    with tar:
        yield tar, stream


@contextmanager
def _readable(what: str = "") -> Iterator[None]:
    """Turn what a damaged gzip or tar stream raises into ``InvalidBody``."""
    try:
        yield
    except _DAMAGED as error:
        raise InvalidBody(
            f"the archive cannot be read{f' ({what})' if what else ''}: {error}"
        ) from error


def _member(members: Iterator[tarfile.TarInfo], name: str) -> tarfile.TarInfo:
    """The next archive member, which must be the regular file ``name``."""
    with _readable():
        member = next(members, None)
    if member is None or member.name != name:
        raise InvalidBody(
            f"the archive's next member must be {name}, not {member and member.name!r}"
        )
    if not member.isfile():
        raise InvalidBody(f"the archive member {name} is not a regular file")
    return member


def _read(tar: tarfile.TarFile, member: tarfile.TarInfo, what: str) -> bytes:
    with _readable(what):
        file = tar.extractfile(member)
        assert file is not None, "a regular file has content"
        return file.read()


def _manifest(tar: tarfile.TarFile, members: Iterator[tarfile.TarInfo]) -> TenantDump:
    text = _read(tar, _member(members, MANIFEST), MANIFEST)
    try:
        return TenantDump.model_validate_json(text)
    except ValueError as error:  # pydantic's ValidationError, or bytes that are not JSON
        raise InvalidBody(f"{MANIFEST} is not a tenant dump manifest: {error}") from error


def _check_manifest(manifest: TenantDump, view: SchemaView, iris: Iris) -> None:
    """PD-5, first half: what the manifest alone tells (the service's policy and schema against the dump's)."""
    if manifest.format_version != FORMAT_VERSION:
        raise InvalidBody(
            f"the dump has format version {manifest.format_version}, this service reads {FORMAT_VERSION}"
        )
    dumped, own = (
        (manifest.schema_id, manifest.schema_version),
        (view.schema.id, view.schema.version),
    )
    if dumped != own:
        raise InvalidBody(
            f"the dump is of schema {dumped[0]} version {dumped[1]}, this service has {own[0]} version {own[1]}"
        )
    if differing := policy_differences(manifest.iri_policy, iris.effective_policy):
        raise InvalidBody(
            f"the dump was made under another IRI policy: {', '.join(differing)} differ"
        )
    if glued := glued_templates(iris.effective_policy):
        raise InvalidBody(
            f"the IRI policy puts the tenant id next to a letter, a digit or a variable in {', '.join(glued)}, so a dump cannot be moved to a new tenant"
        )
    try:
        consistent = iris.tenant_id_of(manifest.source_tenant) == manifest.source_tenant_id
    except InvalidIri:
        consistent = False
    if not consistent:
        raise InvalidBody(
            f"{manifest.source_tenant} is not a tenant with id {manifest.source_tenant_id}"
        )


def _moved(quads: bytes, manifest: TenantDump, tenant: str, iris: Iris) -> Dataset:
    """The quads parsed and moved from the source tenant to ``tenant``."""
    parsed = Dataset()
    try:
        parsed.parse(data=quads, format=NQUADS)
    except Exception as error:  # the parser raises its own types for any bad input
        raise InvalidBody(f"{GRAPHS} is not N-Quads: {error}") from error
    return rewrite(parsed, iris.settings.base, manifest.source_tenant_id, iris.tenant_id_of(tenant))


def _check_graphs(data: Dataset, tenant: str, iris: Iris) -> None:
    """PD-5, second half: every quad is in a graph the policy mints for ``tenant``, none in the default graph."""
    minted = {iris.meta(tenant), iris.registry(tenant)}
    for graph in sorted({str(graph) for *_, graph in data.quads()}):
        if graph == str(DATASET_DEFAULT_GRAPH_ID):
            raise InvalidBody("the dump has a quad in the default graph")
        if not (
            URIRef(graph) in minted
            or iris.is_aggregate_graph(tenant, graph)
            or iris.is_loaded_graph(tenant, graph)
        ):
            raise InvalidBody(
                f"the dump has a quad in the graph {graph}, which the IRI policy does not mint for a tenant"
            )


def _blobs(
    tar: tarfile.TarFile, members: Iterator[tarfile.TarInfo], stream: gzip.GzipFile
) -> Iterator[tuple[str, bytes]]:
    """The ``(key, bytes)`` of each remaining member, read as it is asked for.

    A member that is not a blob, a key that climbs (a ``.`` or ``..`` segment) or repeats, a name that is not
    UTF-8, or a gzip stream that does not end with its marker is ``InvalidBody`` (PD-3, PD-12).
    """
    seen: set[str] = set()
    while True:
        with _readable():
            member = next(members, None)
        if member is None:
            if tar.fileobj.tell() == tar.offset:  # the stream ended where an end block should be
                raise InvalidBody("the archive has no tar end blocks: it is cut short")
            with _readable("the gzip stream does not end properly"):
                while stream.read(1 << 16):  # verifies the CRC and the length at the end
                    pass
            return
        key = member.name.removeprefix(BLOBS)
        if not member.name.startswith(BLOBS) or not key or not member.isfile():
            raise InvalidBody(
                f"the archive member {member.name!r} is not a blob: a regular file under {BLOBS}"
            )
        _check_key(key, member.name, seen)
        yield key, _read(tar, member, member.name)


def _check_key(key: str, name: str, seen: set[str]) -> None:
    """PD-12 F2 to F4: a blob key that is UTF-8, climbs nowhere and was not seen before."""
    try:
        name.encode("utf-8")  # tarfile decodes with surrogateescape, so a stray byte shows here
    except UnicodeEncodeError as error:
        raise InvalidBody(f"the archive member name {name!r} is not UTF-8") from error
    if {".", ".."} & set(key.split("/")):
        raise InvalidBody(f"the blob key {key!r} has a '.' or '..' path segment")
    if key in seen:
        raise InvalidBody(f"the archive holds the blob {key!r} twice")
    seen.add(key)
