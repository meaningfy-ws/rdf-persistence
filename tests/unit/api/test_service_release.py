"""A service no longer referenced is freed, with no help from ``typing``'s caches (test-memory-followups PD-1)."""

import gc

from rdf_persistence.api.entrypoints.kit import ServiceKit
from rdf_persistence.testkit import clear_caches
from tests.toy_service import ToyService


def live_kits() -> int:
    gc.collect()
    return sum(isinstance(o, ServiceKit) for o in gc.get_objects())


def test_a_dropped_service_is_freed_without_clearing_typing() -> None:
    clear_caches()  # a kit an earlier test left in a cache is not this test's
    before = live_kits()
    services = [ToyService() for _ in range(3)]
    assert live_kits() >= before + 3, "the three services are alive"
    del services
    clear_caches(include_typing=False)
    assert live_kits() == before, "no ServiceKit outlives its dropped service, typing caches kept"
