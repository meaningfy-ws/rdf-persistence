"""Docker containers for tests: Fuseki, Garage and Zitadel (PD-16).

Importing this package needs the extra ``rdf-persistence[testkit]``. The pytest plugin is
``rdf_persistence.testkit.containers.fixtures``.
"""

try:
    import testcontainers  # noqa: F401
except ImportError as error:
    raise ImportError(
        "rdf_persistence.testkit.containers needs the optional dependency testcontainers; "
        "install it with: pip install 'rdf-persistence[testkit]'"
    ) from error
