"""What the graph-loading tests share: the tenant and the aggregate a graph is loaded for.

Not collected as tests; the loading tests and their format attacks import from here.
"""

from uuid import UUID

TENANT = "https://example.org/libraries/6f1c"
AGGREGATE = f"{TENANT}/books/{UUID(int=1)}"
