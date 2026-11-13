"""FakeFileStore: the behaviour of the file store port that the services rely on, and its failure injection."""

import inspect

import pytest

from rdf_persistence.domain.exceptions import Conflict, NotFound, StoreUnavailable, TenantGone
from rdf_persistence.testkit import FakeFileStore, no_network  # noqa: F401  (fixture)
from rdf_persistence.testkit.file_store_conformance import CASES, run_case


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_the_fake_file_store_conforms(case, no_network):  # noqa: F811
    await run_case(case, FakeFileStore())


@pytest.fixture
async def files(no_network) -> FakeFileStore:  # noqa: F811
    fake = FakeFileStore()
    await fake.create_bucket("b")
    return fake


async def test_a_blob_comes_back_byte_for_byte(files):
    await files.put("b", "k", b"\x00\xffbytes")
    assert await files.get("b", "k") == b"\x00\xffbytes"


async def test_a_deleted_blob_is_gone_and_deleting_it_again_is_harmless(files):
    await files.put("b", "k", b"x")
    await files.delete("b", "k")
    await files.delete("b", "k")
    with pytest.raises(NotFound):
        await files.get("b", "k")


async def test_a_bucket_is_created_once(files):
    with pytest.raises(Conflict):
        await files.create_bucket("b")


async def test_buckets_are_listed_by_prefix_in_name_order(files):
    for name in ("lib-t-2", "lib-t-1", "other-1"):
        await files.create_bucket(name)
    assert await files.list_buckets("lib-t-") == ["lib-t-1", "lib-t-2"]


async def test_deleting_a_bucket_removes_its_blobs_and_the_bucket(files):
    await files.put("b", "k", b"x")
    await files.delete_bucket("b")
    assert await files.list_buckets("") == [], "the bucket is gone"
    with pytest.raises(TenantGone):
        await files.get("b", "k")


async def test_deleting_a_missing_bucket_is_not_found(files):
    with pytest.raises(NotFound):
        await files.delete_bucket("missing")


@pytest.mark.parametrize("operation", ["put", "get", "delete"])
async def test_an_object_operation_on_a_missing_bucket_is_tenant_gone_and_creates_nothing(
    files, operation
):
    arguments = {"put": ("missing", "k", b"x"), "get": ("missing", "k"), "delete": ("missing", "k")}
    with pytest.raises(TenantGone):
        await getattr(files, operation)(*arguments[operation])
    assert await files.list_buckets("missing") == [], "no bucket was created"


@pytest.mark.parametrize("key", ["a\nb", "../x", ""], ids=repr)
async def test_a_put_of_a_key_the_object_store_refuses_is_refused_and_stores_nothing(files, key):
    with pytest.raises(ValueError, match="key"):
        await files.put("b", key, b"x")
    assert await files.list_blobs("b") == [], "the fake refuses as Garage does"


async def test_an_injected_error_is_raised_once_and_sent_records_the_failed_call(files):
    files.on("create_bucket", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await files.create_bucket("c")
    await files.create_bucket("c")
    assert files.sent("create_bucket") == ["b", "c", "c"]


async def test_an_injected_error_can_wait_for_later_calls(files):
    files.on("create_bucket", StoreUnavailable("down"), after=1)
    await files.create_bucket("c")
    with pytest.raises(StoreUnavailable):
        await files.create_bucket("d")
    assert await files.list_buckets("") == ["b", "c"]


@pytest.mark.parametrize("call", ["on", "sent"])
def test_a_misspelt_operation_is_refused_not_silently_ignored(call):
    files = FakeFileStore()
    args = (StoreUnavailable("down"),) if call == "on" else ()
    with pytest.raises(ValueError, match="delete_buckets"):
        getattr(files, call)("delete_buckets", *args)


def test_the_known_operations_are_exactly_the_async_methods_of_the_fake():
    methods = {
        name
        for name in dir(FakeFileStore)
        if not name.startswith("_") and inspect.iscoroutinefunction(getattr(FakeFileStore, name))
    }
    assert methods == FakeFileStore.OPERATIONS, "an operation was added or removed without the list"
