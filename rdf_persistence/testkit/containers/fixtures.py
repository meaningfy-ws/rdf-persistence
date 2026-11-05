"""pytest plugin: starts the containers a test's markers need (PD-16).

Enable it from a conftest's ``pytest_configure`` with
``config.pluginmanager.import_plugin("rdf_persistence.testkit.containers.fixtures")`` (pytest allows
``pytest_plugins`` only in the rootdir conftest), or with ``-p``. A test marked ``store``,
``files`` or ``identity`` gets Fuseki, Garage or Zitadel started once per session; a test without
those markers starts nothing. Tests may also ask for the ``fuseki``, ``garage`` or ``zitadel``
fixture directly. Needs Docker and the extra ``rdf-persistence[testkit]``.
"""

import socket
import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import httpx
import pytest
from testcontainers.compose import DockerCompose

from rdf_persistence.testkit.bootstrap import (
    environment,
    redact_secrets,
    value_after,
    wait_until,
)
from rdf_persistence.testkit.markers import (
    FUSEKI,
    GARAGE,
    ZITADEL,
    containers_for,
    register_markers,
)

COMPOSE_DIR = Path(__file__).parent
COMPOSE_FILE = "compose.yaml"
POSTGRES = "postgres"
ZITADEL_FILES = "zitadel-files"  # holds the volume the first-instance setup writes the PAT to

# The user admitted by fuseki/shiro.ini; change both together.
FUSEKI_USER = ("rp-test", "rp-test")
GARAGE_REGION = "garage"
GARAGE_KEY_NAME = "rp-test"
GARAGE_BINARY = "/garage"
GARAGE_ZONE = "dc1"
GARAGE_CAPACITY = "1G"
GARAGE_LAYOUT_VERSION = "1"
GARAGE_KEY_ID_LABEL = "key id"
GARAGE_SECRET_LABEL = "secret key"
ZITADEL_PAT_PATH = "/bootstrap/admin.pat"
HTTP_ERRORS = (httpx.HTTPError, OSError)


def pytest_configure(config: pytest.Config) -> None:
    """Register the container markers, for consumers that do not list them in ``pytest.ini``."""
    register_markers(config)


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


@pytest.fixture(scope="session")
def _compose_project() -> Iterator[None]:
    """Give this session its own compose project, so parallel runs never share containers."""
    with environment(COMPOSE_PROJECT_NAME=f"rp-test-{uuid.uuid4().hex[:8]}"):
        yield


@contextmanager
def _running(
    *services: str, port_var: str, build: bool = False
) -> Iterator[tuple[DockerCompose, int]]:
    """Start the services on a free host port, and tear down and restore the environment after.

    The port reaches ``compose.yaml`` through the ``port_var`` variable.
    """
    port = _free_port()
    with (
        environment(**{port_var: str(port)}),
        DockerCompose(
            COMPOSE_DIR,
            compose_file_name=COMPOSE_FILE,
            services=list(services),
            build=build,
            quiet_build=True,
        ) as compose,
    ):
        yield compose, port


class ExecResult(NamedTuple):
    """What a command run inside a container printed, and how it ended."""

    out: str
    err: str
    code: int


def _exec(compose: DockerCompose, service: str, command: list[str]) -> ExecResult:
    """Run a command in a container and report its outcome; a failing command does not raise."""
    try:
        return ExecResult(*compose.exec_in_container(command, service_name=service))
    except subprocess.CalledProcessError as error:
        return ExecResult(
            (error.stdout or b"").decode(), (error.stderr or b"").decode(), error.returncode
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
    with _running(FUSEKI, port_var="RP_FUSEKI_PORT", build=True) as (_, port):
        server = FusekiServer(url=f"http://localhost:{port}", auth=FUSEKI_USER)
        wait_until(
            lambda: httpx.get(f"{server.url}/$/ping", auth=server.auth).is_success,
            "Fuseki",
            retry_on=HTTP_ERRORS,
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
    secret: str = field(repr=False)
    region: str = GARAGE_REGION


def _garage_cli(compose: DockerCompose, *args: str) -> ExecResult:
    return _exec(compose, GARAGE, [GARAGE_BINARY, *args])


def _garage_node_id(compose: DockerCompose) -> str:
    """The node id, or ``""`` while Garage's RPC is not up yet."""
    result = _garage_cli(compose, "node", "id", "-q")
    return result.out.strip().split("@")[0] if result.code == 0 else ""


def _garage_require(compose: DockerCompose, *args: str) -> str:
    """Run a Garage command that must succeed; the error never carries its output's secrets."""
    result = _garage_cli(compose, *args)
    if result.code:
        raise RuntimeError(
            f"garage {' '.join(args[:2])} failed with exit code {result.code}: "
            f"{redact_secrets(result.err)}"
        )
    return result.out


def _bootstrap_garage(compose: DockerCompose) -> tuple[str, str]:
    """Assign and apply a one-node layout, then create a key; return its id and secret."""
    node = wait_until(lambda: _garage_node_id(compose), "Garage RPC")
    _garage_require(compose, "layout", "assign", "-z", GARAGE_ZONE, "-c", GARAGE_CAPACITY, node)
    _garage_require(compose, "layout", "apply", "--version", GARAGE_LAYOUT_VERSION)
    created = _garage_require(compose, "key", "create", GARAGE_KEY_NAME)
    _garage_require(compose, "key", "allow", "--create-bucket", GARAGE_KEY_NAME)
    return value_after(GARAGE_KEY_ID_LABEL, created), value_after(GARAGE_SECRET_LABEL, created)


@pytest.fixture(scope="session")
def garage(_compose_project: None) -> Iterator[GarageServer]:
    """Garage with a one-node layout and one key allowed to create buckets."""
    with _running(GARAGE, port_var="RP_GARAGE_PORT") as (compose, port):
        key_id, secret = _bootstrap_garage(compose)
        yield GarageServer(endpoint=f"http://localhost:{port}", key_id=key_id, secret=secret)


# ---------------------------------------------------------------------------
# Zitadel
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZitadelServer:
    """Where the test Zitadel answers, and the admin machine user's personal access token.

    ``admin_pat`` authenticates the management API, for provisioning a project, an application
    and machine users in the test instance.
    """

    url: str
    admin_pat: str = field(repr=False)


def _management_answers(server: ZitadelServer) -> bool:
    response = httpx.get(
        f"{server.url}/management/v1/orgs/me",
        headers={"Authorization": f"Bearer {server.admin_pat}"},
    )
    return response.is_success


def _read_pat(compose: DockerCompose) -> str:
    """The PAT that first-instance setup wrote, or ``""`` until it exists.

    Zitadel's image has no shell, so a helper container that shares the volume reads it.
    """
    result = _exec(compose, ZITADEL_FILES, ["cat", ZITADEL_PAT_PATH])
    return result.out.strip() if result.code == 0 else ""


@pytest.fixture(scope="session")
def zitadel(_compose_project: None) -> Iterator[ZitadelServer]:
    """Zitadel with Postgres, and the PAT that first-instance setup wrote to its volume."""
    with _running(ZITADEL, POSTGRES, ZITADEL_FILES, port_var="RP_ZITADEL_PORT") as (compose, port):
        pat = wait_until(lambda: _read_pat(compose), "Zitadel's token file")
        server = ZitadelServer(url=f"http://localhost:{port}", admin_pat=pat)
        # The health check passes before the management API can reach Zitadel's own gRPC port.
        wait_until(
            lambda: _management_answers(server), "Zitadel's management API", retry_on=HTTP_ERRORS
        )
        yield server
