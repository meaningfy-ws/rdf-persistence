"""The one lock that makes rdflib's SPARQL parser safe to call from several threads.

rdflib's SPARQL grammar is a set of module-level pyparsing objects. pyparsing finds the arity of each
parse action on its first call, in a counter it shares between threads; two threads in that first call
overshoot it, and the action fails with ``TypeError: ... missing 1 required positional argument`` for the
rest of the process (pyparsing 3.3, ``_trim_arity``). Hold ``SPARQL_PARSER_LOCK`` around every call that
makes rdflib parse SPARQL text: ``prepareQuery``, ``prepareUpdate``, ``parseQuery``, ``parseUpdate``,
``Graph.query`` or ``Graph.update`` with a string, and pyshacl's ``validate``, which parses the SPARQL
of the shapes it checks. Parsing and validating are CPU-bound, so the lock costs no parallelism.
"""

import threading

SPARQL_PARSER_LOCK = threading.RLock()
