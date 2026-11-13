"""Moving a tenant's quads to a new tenant id: the pure part of a restore (tenant-dump-restore PD-4, PD-5, PD-13).

``rewrite`` carries a dump's IRIs to the new tenant, ``glued_templates`` names the IRI policies it cannot
handle and ``check_graphs`` refuses quads that are not in a graph the policy mints for the new tenant. No I/O.
"""

import re

from rdflib import Dataset, URIRef
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.term import Node

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.generated.service.rp_service import IriPolicy
from rdf_persistence.domain.iris import Iris

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


def check_graphs(data: Dataset, tenant: str, iris: Iris) -> None:
    """Every quad of ``data`` is in a graph the policy mints for ``tenant``, none in the default graph.

    Raises:
        InvalidBody: A quad is in the default graph or in a graph that is not the tenant's.
    """
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
