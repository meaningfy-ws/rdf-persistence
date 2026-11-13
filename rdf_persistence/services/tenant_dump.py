"""Move a tenant's quads to a new tenant id: the pure part of dump and restore (tenant-dump-restore PD-4)."""

import re

from rdflib import Dataset, URIRef
from rdflib.term import Node

from rdf_persistence.domain.generated.service.rp_service import IriPolicy

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
