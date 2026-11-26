"""A test worker releases memory between test modules (PD-9): the caches, the hook's decision, the effect."""

import gc
from types import SimpleNamespace

import pytest

from rdf_persistence.api.entrypoints.kit import ServiceKit
from rdf_persistence.testkit import clear_caches, release_memory
from rdf_persistence.testkit.memory import CacheCounts, after_test
from tests.toy_service import ToyService


def live_kits() -> int:
    gc.collect()
    return sum(isinstance(o, ServiceKit) for o in gc.get_objects())


def test_clear_caches_finds_a_cache_in_each_library() -> None:
    counts = clear_caches()
    assert counts["linkml_runtime"] >= 1, (
        "no lru_cache found on SchemaView: linkml-runtime renamed them"
    )
    assert counts["fastapi"] >= 1, (
        "no lru_cache found in fastapi.dependencies.models: FastAPI renamed them"
    )
    assert counts["typing"] >= 1, "no cache cleanup found in typing: CPython renamed _cleanups"


def test_clear_caches_can_leave_typing_alone() -> None:
    counts = clear_caches(typing=False)
    assert counts["typing"] == 0, "typing=False clears no typing cache"
    assert counts["linkml_runtime"] >= 1, "SchemaView caches are still cleared"
    assert counts["fastapi"] >= 1, "FastAPI caches are still cleared"


def test_release_reports_the_caches_it_cleared() -> None:
    counts: CacheCounts = release_memory()
    assert counts["linkml_runtime"] >= 1, "release clears linkml-runtime"
    assert counts["fastapi"] >= 1, "release clears FastAPI"


def test_release_leaves_no_service_kit_of_dropped_services() -> None:
    release_memory()  # a kit an earlier test left in a cache is not this test's
    before = live_kits()
    services = [ToyService() for _ in range(3)]
    assert live_kits() >= before + 3, "the three services are alive"
    del services
    release_memory()
    assert live_kits() == before, "no ServiceKit outlives its dropped service after release"


def _item(module: object) -> SimpleNamespace:
    return SimpleNamespace(module=module)


A, B = object(), object()


@pytest.mark.parametrize(
    ("nextitem", "environ", "expected"),
    [
        (_item(A), {}, ["clear"]),
        (_item(B), {}, ["clear", "release"]),
        (None, {}, ["clear", "release"]),
        (_item(A), {"TEST_RELEASE": "off"}, []),
        (_item(B), {"TEST_RELEASE": "off"}, []),
        (None, {"TEST_RELEASE": "off"}, []),
        (_item(B), {"TEST_RELEASE": "on"}, ["clear", "release"]),
    ],
    ids=["same-module", "next-module", "last", "off-same", "off-next", "off-last", "on"],
)
def test_after_test_decides_what_to_run(
    nextitem: SimpleNamespace | None, environ: dict[str, str], expected: list[str]
) -> None:
    calls: list[str] = []
    after_test(
        _item(A),
        nextitem,
        clear=lambda: calls.append("clear"),
        release=lambda: calls.append("release"),
        environ=environ,
    )
    assert calls == expected, "the calls made after a test"


def test_after_test_never_fails_a_test() -> None:
    def broken() -> None:
        raise RuntimeError("cache gone")

    after_test(_item(A), None, clear=broken, release=broken, environ={})


def test_module_scoped_service_is_gone_after_the_modules_last_test(
    pytester: pytest.Pytester, tmp_path
) -> None:
    pytester.makeconftest('pytest_plugins = ["rdf_persistence.testkit.memory_plugin"]\n')
    report = tmp_path / "kits.txt"
    pytester.makepyfile(
        test_a="""
        import pytest
        from tests.toy_service import ToyService

        @pytest.fixture(scope="module")
        def service():
            return ToyService()

        def test_uses_it(service):
            assert service.kit
        """,
        test_b=f"""
        import gc
        from rdf_persistence.api.entrypoints.kit import ServiceKit

        def test_none_alive():
            gc.collect()
            n = sum(isinstance(o, ServiceKit) for o in gc.get_objects())
            open({str(report)!r}, "w").write(str(n))
        """,
    )
    release_memory()
    before = live_kits()
    result = pytester.runpytest_inprocess(
        "-p", "no:randomly", "-n", "0", "--no-cov", "-p", "no:cacheprovider"
    )
    result.assert_outcomes(passed=2)
    assert int(report.read_text()) <= before, "no kit of the first module is alive in the second"
