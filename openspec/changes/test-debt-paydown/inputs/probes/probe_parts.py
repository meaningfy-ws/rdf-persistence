"""Unprofiled timings of the parts of ToyService(): shapes parse, rebuild from cached triples, schema view work, copy."""
import copy, sys, time
sys.path.insert(0, ".")
from rdflib import Graph
from tests.toy_service import ToyService
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services import documents as d
import tests.toy as toy

ToyService()
def t(label, fn, n=10):
    s = time.perf_counter()
    for _ in range(n): r = fn()
    print(f"{label:55s} {(time.perf_counter()-s)/n*1000:7.1f} ms"); return r
folder = ToyService().kit.generated_folder
print("generated folder:", folder)
shapes_path = folder / d.SHAPES_FILE
g = t("parse shapes (Turtle)", lambda: Graph().parse(shapes_path))
print("shape triples:", len(g))
triples = tuple(g)
def rebuild():
    h = Graph(); h.addN((s, p, o, h) for s, p, o in triples); return h
t("rebuild Graph from cached triples (addN)", rebuild)
t("copy.deepcopy? skipped; Graph + cached graph", lambda: Graph() + g)
t("load_schema + iri_types (fresh view)", lambda: iri_types(load_schema(toy.TOY_SCHEMA)))
v = load_schema(toy.TOY_SCHEMA); iri_types(v)
t("iri_types on a warm view", lambda: iri_types(v))
t("ToyService() whole", ToyService, 5)
