"""pytest plugin: starts the containers a test's markers need (PD-16).

Enable it with ``pytest_plugins = ["rdf_persistence.testkit.containers.fixtures"]``. A test marked
``store``, ``files`` or ``identity`` gets Fuseki, Garage or Zitadel started once per session; a test
without those markers starts nothing. Tests may also ask for the ``fuseki``, ``garage`` or
``zitadel`` fixture directly. Needs Docker and the extra ``rdf-persistence[testkit]``.
"""

import os
import socket
import stat
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from testcontainers.compose import DockerCompose

COMPOSE_DIR = Path(__file__).parent
COMPOSE_FILE = "compose.yaml"

STORE, FILES, IDENTITY = "store", "files", "identity"
FUSEKI, GARAGE, ZITADEL, POSTGRES = "fuseki", "garage", "zitadel", "postgres"
CONTAINER_BY_MARKER = {STORE: FUSEKI, FILES: GARAGE, IDENTITY: ZITADEL}
MARKER_HELP = {
    STORE: "needs the Fuseki container",
    FILES: "needs the Garage container",
    IDENTITY: "needs the Zitadel container",
}

FUSEKI_USER = ("rp-test", "rp-test")
GARAGE_REGION = "garage"
GARAGE_KEY_NAME = "rp-test"
START_TIMEOUT_SECONDS = 180


def containers_for(markers: Iterable[str]) -> list[str]:
    """Return the containers the given markers need, in a stable order."""
    wanted = {CONTAINER_BY_MARKER[m] for m in markers if m in CONTAINER_BY_MARKER}
    return [c for c in CONTAINER_BY_MARKER.values() if c in wanted]


def pytest_configure(config: pytest.Config) -> None:
    """Register the container markers, for consumers that do not list them in ``pytest.ini``."""
    for marker, help_text in MARKER_HELP.items():
        config.addinivalue_line("markers", f"{marker}: {help_text}")


@pytest.fixture(autouse=True)
def _containers_for_markers(request: pytest.FixtureRequest) -> None:
    """Start the containers that the test's markers name."""
    markers = [m.name for m in request.node.iter_markers()]
    for container in containers_for(markers):
        request.getfixturevalue(container)


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until(probe: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            if probe():
                return
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(1)
    raise TimeoutError(f"{what} did not answer within {START_TIMEOUT_SECONDS}s")


@pytest.fixture(scope="session")
def _compose_project() -> Iterator[None]:
    """Give this session its own compose project, so parallel runs never share containers."""
    os.environ["COMPOSE_PROJECT_NAME"] = f"rp-test-{uuid.uuid4().hex[:8]}"
    yield
    del os.environ["COMPOSE_PROJECT_NAME"]


def _compose(*services: str, build: bool = False) -> DockerCompose:
    return DockerCompose(
        COMPOSE_DIR,
        compose_file_name=COMPOSE_FILE,
        services=list(services),
        build=build,
        quiet_build=True,
    )


# ---------------------------------------------------------------------------
# Fuseki
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FusekiServer:
    """Where the test Fuseki answers, and the one user it admits."""

    url: str
    auth: tuple[str, str]


@pytest.fixture(scope="session")
def fuseki(_compose_project: None) -> Iterator[FusekiServer]:
    """Fuseki, answering ``/$/ping`` for the test user."""
    port = _free_port()
    os.environ["RP_FUSEKI_PORT"] = str(port)
    server = FusekiServer(url=f"http://localhost:{port}", auth=FUSEKI_USER)
    with _compose(FUSEKI, build=True):
        _wait_until(
            lambda: httpx.get(f"{server.url}/$/ping", auth=server.auth).is_success, "Fuseki"
        )
        yield server


# ---------------------------------------------------------------------------
# Garage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GarageServer:
    """The S3 endpoint of the test Garage and the key bootstrapped on it."""

    endpoint: str
    key_id: str
    secret: str
    region: str = GARAGE_REGION


def _value_after(label: str, output: str) -> str:
    for line in output.splitlines():
        if line.strip().lower().startswith(label):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"no '{label}' in garage output:\n{output}")


def _bootstrap_garage(compose: DockerCompose) -> tuple[str, str]:
    """Assign and apply a one-node layout, then create a key; return its id and secret."""

    def garage(*args: str) -> str:
        out, err, code = compose.exec_in_container(["/garage", *args], service_name=GARAGE)
        if code:
            raise RuntimeError(f"garage {' '.join(args)} failed: {err or out}")
        return str(out)

    _wait_until(lambda: bool(garage("node", "id", "-q")), "Garage RPC")
    node = garage("node", "id", "-q").strip().split("@")[0]
    garage("layout", "assign", "-z", "dc1", "-c", "1G", node)
    garage("layout", "apply", "--version", "1")
    created = garage("key", "create", GARAGE_KEY_NAME)
    garage("key", "allow", "--create-bucket", GARAGE_KEY_NAME)
    return _value_after("key id", created), _value_after("secret key", created)


@pytest.fixture(scope="session")
def garage(_compose_project: None) -> Iterator[GarageServer]:
    """Garage with a one-node layout and one key allowed to create buckets."""
    port = _free_port()
    os.environ["RP_GARAGE_PORT"] = str(port)
    with _compose(GARAGE) as compose:
        key_id, secret = _bootstrap_garage(compose)
        yield GarageServer(endpoint=f"http://localhost:{port}", key_id=key_id, secret=secret)


# ---------------------------------------------------------------------------
# Zitadel
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZitadelServer:
    """Where the test Zitadel answers, and the admin machine user's personal access token.

    Task 3.3 adds the provisioning (project, JWT application, machine users and their keys)
    on top of this fixture, through the management API with ``admin_pat``.
    """

    url: str
    admin_pat: str


def _management_answers(server: ZitadelServer) -> bool:
    response = httpx.get(
        f"{server.url}/management/v1/orgs/me",
        headers={"Authorization": f"Bearer {server.admin_pat}"},
    )
    return response.is_success


@pytest.fixture(scope="session")
def zitadel(_compose_project: None) -> Iterator[ZitadelServer]:
    """Zitadel with Postgres, and the PAT that first-instance setup wrote to the mounted file."""
    port = _free_port()
    os.environ["RP_ZITADEL_PORT"] = str(port)
    with tempfile.TemporaryDirectory(prefix="rp-zitadel-") as bootstrap_dir:
        # The Zitadel user is not ours; it must be able to write the token here.
        os.chmod(bootstrap_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        os.environ["RP_ZITADEL_BOOTSTRAP_DIR"] = bootstrap_dir
        pat_file = Path(bootstrap_dir) / "admin.pat"
        with _compose(ZITADEL, POSTGRES):
            _wait_until(
                lambda: pat_file.exists() and pat_file.stat().st_size > 0, "Zitadel's token file"
            )
            server = ZitadelServer(
                url=f"http://localhost:{port}", admin_pat=pat_file.read_text().strip()
            )
            # The health check passes before the management API can reach Zitadel's own gRPC port.
            _wait_until(lambda: _management_answers(server), "Zitadel's management API")
            yield server
