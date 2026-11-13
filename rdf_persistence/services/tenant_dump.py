"""Dump a tenant to one archive and restore an archive into a new tenant (tenant-dump-restore).

The archive is a gzipped tar read and written as a stream: ``manifest.json`` (a ``TenantDump``), ``graphs.nq``
(every named graph of the tenant's database), ``blobs/<key>`` for each blob of its bucket, and last the empty
member ``end``, which tells a whole archive from one cut short. A restore reads the archive here (its layout, the
manifest, the N-Quads, the blobs, a decompression budget) and checks the manifest before anything is created, so a
refused dump leaves nothing behind (PD-5); ``Tenancy.restore`` moves the quads to the new tenant, checks them and
writes the new tenant, and cleans up if anything fails (PD-6, PD-13).

shortcut: ``src`` and ``out`` are read and written synchronously on the caller's thread, a blob is held whole in
memory while it is read or written, and the N-Quads are one ``bytes``; stream them in chunks and move the archive
off the event loop once a tenant outgrows memory or the loop's latency.
"""

import gzip
import io
import logging
import tarfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import BinaryIO

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import Dataset
from rdflib.exceptions import ParserError

from rdf_persistence.domain.blob_keys import checked_blob_key
from rdf_persistence.domain.exceptions import Conflict, InvalidBody, InvalidIri, NotFound
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import TenantDump, TenantSummary
from rdf_persistence.domain.iris import Iris, policy_differences
from rdf_persistence.domain.media import N_QUADS
from rdf_persistence.domain.tenant_move import glued_templates
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.session import Clock, utc_now
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)

FORMAT_VERSION = 1
MANIFEST, GRAPHS, BLOBS, END = "manifest.json", "graphs.nq", "blobs/", "end"
MAX_MANIFEST_BYTES = (
    64 * 1024
)  # a manifest is a few hundred bytes plus the policy; this is generous
# Beyond ``max_bytes`` the wrapper still lets through the tar's own overhead that the per-member charge does not
# count: the long-name and extended header blocks, the two zero blocks and the record padding at the end (PD-13).
HEADER_ALLOWANCE = 4 * tarfile.RECORDSIZE
# What a damaged gzip or tar stream raises while it is read.
_DAMAGED = (tarfile.TarError, gzip.BadGzipFile, EOFError, zlib.error)


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
    known to be active and its graphs are read. The archive ends with the empty member ``end``. One line is
    logged (step ``dump``, the tenant and the blob count), no content. Writing to ``out`` blocks.

    Raises:
        NotFound: The tenant has no access record.
        Conflict: The tenant is being deleted.
    """
    record, _ = await tenancy.get(tenant)
    if record.state == TenantState.DELETING:
        raise Conflict(f"{tenant} is being deleted")
    database = record.database_name
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
    written = 0
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
            written += 1
        _add(tar, END, b"", stamp.timestamp())
    log.info("dump", extra={"step": "dump", "tenant": tenant, "blobs": written})
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


# -- restore (PD-3, PD-5, PD-6, PD-13) ----------------------------------------------------------------


class _Budget:
    """The bytes a restore may still read: each member costs its header block plus its size padded to a block (PD-13, PD-14).

    A gzip bomb is a few kilobytes that decompress to gigabytes; the header of each member says its size before
    any of it is read, so the archive is refused before the memory or the object store is filled.
    """

    def __init__(self, limit: int) -> None:
        self._limit, self.left = limit, limit

    def charge(self, size: int) -> None:
        self.left -= size
        if self.left < 0:
            raise InvalidBody(
                f"the archive holds more than {self._limit} bytes once decompressed, more than this service restores"
            )


def _block_cost(size: int) -> int:
    """What a member of ``size`` bytes takes in the tar: its header block and its content padded to a block (PD-14)."""
    return tarfile.BLOCKSIZE + -(-size // tarfile.BLOCKSIZE) * tarfile.BLOCKSIZE


class _Counted:
    """A read-only view of ``stream`` that refuses once more than ``limit`` bytes have been read from it (PD-13).

    ``tarfile`` holds a GNU long name or a pax header whole before the member is seen, so the per-member charge
    misses it; this bounds every read, headers included. ``tarfile`` in stream mode only calls ``read``.
    """

    def __init__(self, stream: gzip.GzipFile, limit: int) -> None:
        self._stream, self._limit, self._seen = stream, limit, 0

    def read(self, size: int) -> bytes:
        chunk = self._stream.read(size)
        self._seen += len(chunk)
        if self._seen > self._limit:
            raise InvalidBody(
                f"the archive holds more than {self._limit} bytes once decompressed, more than this service restores"
            )
        return chunk


async def restore(
    tenancy: Tenancy,
    iris: Iris,
    view: SchemaView,
    src: BinaryIO,
    creator: Principal,
    *,
    max_bytes: int,
) -> TenantSummary:
    """Create a new tenant out of the dump archive in ``src``; ``creator`` is granted the creator role in it.

    The manifest and the quads are read and checked first and nothing is created if they are refused; then
    ``Tenancy.restore`` moves them to the new tenant and writes it, with the blobs read from the stream and stored
    one at a time. ``max_bytes`` bounds what the archive may hold once decompressed (``max_restore_bytes``).
    Reading ``src`` blocks. One line is logged (step ``restore``, the source and the new tenant), no content.

    Raises:
        InvalidBody: The archive is not a dump of this service (its layout, format version, schema, IRI policy,
            graphs or root), is larger than ``max_bytes`` decompressed, or a member among the blobs is not a blob.
        Conflict: The drawn tenant id was taken at the same moment; retry.
        PersistenceError: The tenant could not be created; see ``Tenancy.restore``.
    """
    budget = _Budget(max_bytes)
    with _opened(src, max_bytes + HEADER_ALLOWANCE) as (tar, stream):
        members = iter(tar)
        manifest = _manifest(tar, members, budget)
        _check_manifest(manifest, view, iris)
        parsed = _parsed(tar, _member(members, GRAPHS), budget)
        summary = await tenancy.restore(
            parsed, manifest.source_tenant_id, _blobs(tar, members, stream, budget), creator
        )
    log.info(
        "restore",
        extra={"step": "restore", "tenant": summary.id, "source": manifest.source_tenant},
    )
    return summary


@contextmanager
def _opened(src: BinaryIO, limit: int) -> Iterator[tuple[tarfile.TarFile, gzip.GzipFile]]:
    """The tar and, under it, the gzip stream: that one is read to its end (PD-12 F1), which the tar does not reach.

    The tar reads the stream through ``_Counted``, which refuses past ``limit`` decompressed bytes.
    """
    stream = gzip.GzipFile(fileobj=src)
    with _readable("it is not a gzipped tar"):
        # a stream: members are read in order, never back; closed by the ``with`` below
        tar = tarfile.open(fileobj=_Counted(stream, limit), mode="r|")  # type: ignore[call-overload]  # noqa: SIM115
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
        found = f"the member {member.name!r}" if member else "the end of the archive"
        raise InvalidBody(f"the archive's next member must be {name}, found {found}")
    if not member.isfile():
        raise InvalidBody(f"the archive member {name} is not a regular file")
    return member


def _read(
    tar: tarfile.TarFile,
    member: tarfile.TarInfo,
    what: str,
    budget: _Budget,
    cap: int | None = None,
) -> bytes:
    """The content of ``member``, once its size (from the header) is within ``cap`` and the ``budget``."""
    if cap is not None and member.size > cap:
        raise InvalidBody(
            f"{what} holds {member.size} bytes, more than the {cap // 1024} KiB allowed"
        )
    budget.charge(_block_cost(member.size))
    with _readable(what):
        file = tar.extractfile(member)
        assert file is not None, "a regular file has content"
        return file.read()


def _manifest(
    tar: tarfile.TarFile, members: Iterator[tarfile.TarInfo], budget: _Budget
) -> TenantDump:
    text = _read(tar, _member(members, MANIFEST), MANIFEST, budget, cap=MAX_MANIFEST_BYTES)
    try:
        return TenantDump.model_validate_json(text)
    except ValueError as error:  # pydantic's ValidationError, or bytes that are not JSON
        raise InvalidBody(f"{MANIFEST} is not a tenant dump manifest: {error}") from error


def _parsed(tar: tarfile.TarFile, member: tarfile.TarInfo, budget: _Budget) -> Dataset:
    """The quads of the archive parsed; their bytes are let go when this returns."""
    quads = _read(tar, member, GRAPHS, budget)
    parsed = Dataset()
    try:
        parsed.parse(data=quads, format=N_QUADS)
    except (ParserError, ValueError) as error:  # ValueError: bytes that are not UTF-8
        raise InvalidBody(f"{GRAPHS} is not N-Quads: {error}") from error
    return parsed


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


def _blobs(
    tar: tarfile.TarFile,
    members: Iterator[tarfile.TarInfo],
    stream: gzip.GzipFile,
    budget: _Budget,
) -> Iterator[tuple[str, bytes]]:
    """The ``(key, bytes)`` of each blob member, read as it is asked for; ends once the ``end`` member is checked.

    A member that is not a blob, a key the one key rule refuses (``checked_blob_key``) or that repeats, an archive
    with no ``end`` member after the blobs or with anything after it, a budget overflow, or a gzip stream that does
    not end properly is ``InvalidBody`` (PD-3, PD-12, PD-13).
    """
    seen: set[str] = set()
    while True:
        with _readable():
            member = next(members, None)
        if member is None:
            raise InvalidBody(f"the archive has no {END} member after its blobs: it is cut short")
        if member.name == END:
            _finish(members, stream, member, budget)
            return
        key = member.name.removeprefix(BLOBS)
        if not member.name.startswith(BLOBS) or not key or not member.isfile():
            raise InvalidBody(
                f"the archive member {member.name!r} is not a blob: a regular file under {BLOBS}"
            )
        _check_key(key, seen)
        yield key, _read(tar, member, member.name, budget)


def _check_key(key: str, seen: set[str]) -> None:
    """PD-12 F2 to F4, PD-13: a blob key the one key rule accepts and that was not seen before."""
    try:
        checked_blob_key(key)
    except ValueError as error:
        raise InvalidBody(f"the blob key {key!r} is refused: {error}") from error
    if key in seen:
        raise InvalidBody(f"the archive holds the blob {key!r} twice")
    seen.add(key)


def _finish(
    members: Iterator[tarfile.TarInfo],
    stream: gzip.GzipFile,
    end: tarfile.TarInfo,
    budget: _Budget,
) -> None:
    """The ``end`` member is an empty regular file and the last one; then the gzip stream is read to its trailer."""
    if not end.isfile() or end.size:
        raise InvalidBody(f"the archive member {END} must be an empty regular file")
    budget.charge(_block_cost(0))
    with _readable():
        after = next(members, None)
    if after is not None:
        raise InvalidBody(f"the archive holds the member {after.name!r} after {END}")
    # what is left is the tar's zero blocks and its padding to a record; a bomb hides in more than that
    allowed = budget.left + tarfile.RECORDSIZE
    with _readable("the gzip stream does not end properly"):
        while chunk := stream.read(1 << 16):  # verifies the CRC and the length at the end
            allowed -= len(chunk)
            if allowed < 0:
                raise InvalidBody(
                    f"the archive holds more than {END} and its padding after the blobs"
                )
