"""Profile ToyService() construction: one warm-up, then N profiled constructions."""
import cProfile, pstats, sys, time
sys.path.insert(0, ".")
from tests.toy_service import ToyService

t = time.perf_counter(); ToyService(); first = time.perf_counter() - t
N = 5
t = time.perf_counter()
for _ in range(N): ToyService()
warm = (time.perf_counter() - t) / N
print(f"first construction {first:.3f}s, warm mean {warm:.3f}s over {N}")
pr = cProfile.Profile(); pr.enable()
for _ in range(N): ToyService()
pr.disable()
st = pstats.Stats(pr); st.sort_stats("cumulative"); st.print_stats(45)
st.sort_stats("tottime"); st.print_stats(15)
print("=== callees of ServiceKit.__init__ / Documents.__init__ / install_service")
st.sort_stats("cumulative")
st.print_callees(r"kit.py:94\(__init__\)")
st.print_callees(r"documents.py:93\(__init__\)")
st.print_callees(r"service.py:32\(install_service\)")
st.print_callers(r"schemaview.py:479\(imports_closure\)")
