"""Profile the service fixture's whole set-up: ToyService() plus the lifespan start and stop."""
import asyncio, cProfile, pstats, sys, time
sys.path.insert(0, ".")
from tests.toy_service import ToyService

async def once():
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app):
        pass

async def timed(n):
    t0 = time.perf_counter(); c = 0.0
    for _ in range(n):
        t = time.perf_counter(); toy = ToyService(); c += time.perf_counter() - t
        async with toy.app.router.lifespan_context(toy.app):
            pass
    return (time.perf_counter() - t0) / n, c / n

asyncio.run(once())
total, construct = asyncio.run(timed(5))
print(f"warm mean: whole set-up {total:.3f}s, of which ToyService() {construct:.3f}s, lifespan {total-construct:.3f}s")
pr = cProfile.Profile(); pr.enable(); asyncio.run(timed(5)); pr.disable()
st = pstats.Stats(pr); st.sort_stats("cumulative"); st.print_stats(r"rdf_persistence|tests/", 30)
