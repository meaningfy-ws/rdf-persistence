"""Steps of ``technical_models.feature``: the spec deltas of the technical-models change, end to end.

Each scenario carries its delta scenario in a ``# spec:`` comment. The steps call the same public
API as the unit tests: ``lint-imports`` on a scratch copy of the layers, ``rp-generate`` on a copy of
the toy library or of a small schema, the generated settings, and ``settings_from_env``.
"""

import asyncio
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from pydantic import ValidationError
from pytest_bdd import given, parsers, scenarios, then, when
from rdflib import URIRef

from rdf_persistence.access.adapters.jwks import JwksTokenVerifier
from rdf_persistence.access.services.generated.settings.rp_access_settings import JwksSettings
from rdf_persistence.api.entrypoints.environment import settings_from_env
from rdf_persistence.api.entrypoints.generated.settings.rp_api_settings import ToolkitSettings
from rdf_persistence.core.domain.sparql import term
from rdf_persistence.core.services.generated.rp_core_services import HttpSettings
from rdf_persistence.persistence.adapters.fuseki import FusekiStore
from rdf_persistence.schema.services.generated.templates.rp_schema_templates import RegistryTerms
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit.tokens import ISSUER
from rdf_persistence_generation.cli import main as generate
from tests.import_contracts import Linted, lint_scratch
from tests.toy_service import ToyService

scenarios("technical_models.feature")

ROOT = Path(__file__).parents[2]
TOY = ROOT / "tests" / "fixtures" / "library"
DOMAIN_GENERATED = "core/domain/generated/rp_core.py"
DOMAIN_EXCEPTIONS = "core/domain/exceptions.py"
IRI_LAYOUT = "iris/domain/layout.py"
SERVICE_MODULE = "persistence/services/service_module.py"


def _scratch_module(planted_path: str) -> str:
    """The module a file planted in the scratch copy of the theme layout (the layer contracts) is."""
    return "rdf_persistence." + planted_path.removesuffix(".py").replace("/", ".")


SERVICE_SETTINGS = (
    "rdf_persistence.iris.services.generated.rp_iris_services"  # holds ServiceSettings
)
WIRE = "rdf_persistence.access.adapters.generated.rp_access_adapters"
SETTINGS_MODULE = "rdf_persistence.api.entrypoints.generated.settings.rp_api_settings"
ADAPTER = "rdf_persistence.access.adapters.store"
GENERATED_NAME = "groups"


class Run:
    """What one scenario has built and seen so far."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.planted: dict[str, str] = {}
        self.modules: tuple[str, str] = ("", "")
        self.lint: Linted | None = None
        self.schema_text = ""
        self.project: Path | None = None
        self.package = ""
        self.files_before: dict[str, bytes] = {}
        self.rule = ""
        self.exit_code: int | None = None
        self.output = ""
        self.loaded = False
        self.built: list[object] = []
        self.error: Exception | None = None
        self.environ: dict[str, str] = {}
        self.toolkit: ToolkitSettings | None = None
        self.http: HttpSettings | None = None
        self.jwks: JwksSettings | None = None
        self.probe: subprocess.CompletedProcess[str] | None = None


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return Run(tmp_path)


# --- the architecture of a scratch copy of the layers ---------------------------------------------


def _plant(run: Run, path: str, imports: str, modules: tuple[str, str]) -> None:
    # the imported module is a file of the scratch copy too, so the import is an edge the contract sees
    imported = imports.removeprefix("rdf_persistence.").replace(".", "/") + ".py"
    packages = {
        f"{parent}/__init__.py": "" for parent in map(str, Path(imported).parents) if parent != "."
    }
    run.planted = {path: f"import {imports}\n", imported: "", **packages}
    run.modules = modules


@given("a copy of the toolkit where a generated domain module imports a technical model")
def _generated_domain(run: Run) -> None:
    _plant(
        run,
        DOMAIN_GENERATED,
        SERVICE_SETTINGS,
        (_scratch_module(DOMAIN_GENERATED), SERVICE_SETTINGS),
    )


@given(
    "a copy of the toolkit where the IRI layout module of the domain layer imports the service settings"
)
def _layout(run: Run) -> None:
    # the IRI layout is a module of the `iris` theme's domain layer in the scratch copy of the themes
    _plant(run, IRI_LAYOUT, SERVICE_SETTINGS, (_scratch_module(IRI_LAYOUT), SERVICE_SETTINGS))


@given("a copy of the toolkit where a service module imports an adapter module")
def _service_adapter(run: Run) -> None:
    # a module planted in the scratch copy of the theme layout (the layer contracts), under a name of its own
    run.planted = {
        "access/adapters/store.py": "",
        SERVICE_MODULE: f"import {ADAPTER}\n",
    }
    run.modules = (_scratch_module(SERVICE_MODULE), ADAPTER)


@given("a copy of the toolkit where a service module imports a wire model")
def _service_wire(run: Run) -> None:
    _plant(run, SERVICE_MODULE, WIRE, (_scratch_module(SERVICE_MODULE), WIRE))


@given("a copy of the toolkit where a domain module imports the generated settings")
def _domain_settings(run: Run) -> None:
    run.planted = {DOMAIN_EXCEPTIONS: f"import {SETTINGS_MODULE}\n"}
    run.modules = (_scratch_module(DOMAIN_EXCEPTIONS), SETTINGS_MODULE)


@when("the architecture is checked")
def _check_architecture(run: Run, tmp_path: Path) -> None:
    run.lint = lint_scratch(tmp_path, run.planted)


@then("the check fails")
def _check_fails(run: Run) -> None:
    assert run.lint is not None, "the architecture was checked"
    assert run.lint.code != 0, run.lint.report
    assert run.lint.broken, "a contract is broken"


@then(parsers.re(r"it names the (?P<first>.+) module and the (?P<second>.+) module"))
def _names_both(run: Run) -> None:
    assert run.lint is not None, "the architecture was checked"
    for module in run.modules:
        assert module in run.lint.report, f"{module} is not named: {run.lint.report}"


# --- the schemas a consumer imports ---------------------------------------------------------------

CONSUMER = """\
id: https://example.org/ns/consumer
name: consumer
title: Consumer
description: A schema of a consumer.
prefixes: {{c: "https://example.org/ns/c#", linkml: "https://w3id.org/linkml/"}}
default_prefix: c
default_range: string
imports:
  - linkml:types
  - {imported}
"""


def _load_consumer(run: Run, imported: str) -> int:
    """Load the schema and read its classes, which is when its imports are resolved."""
    path = run.tmp / f"consumer_{imported.rsplit('/', 1)[-1]}.yaml"
    path.write_text(CONSUMER.format(imported=imported), encoding="utf-8")
    return len(load_schema(path).all_classes())


@given(parsers.parse('a consumer schema that imports "{imported}"'))
def _consumer(run: Run, imported: str) -> None:
    run.schema_text = imported


@when("the schema is loaded")
def _load(run: Run) -> None:
    _load_consumer(run, run.schema_text)
    run.loaded = True


@then("it resolves as before")
def _resolves(run: Run) -> None:
    assert run.loaded, "the schema loaded without an error"


@then(parsers.parse('a consumer schema that imports "{imported}" is refused'))
def _refused_import(run: Run, imported: str) -> None:
    with pytest.raises(FileNotFoundError):
        _load_consumer(run, imported)


# --- the kind of a target, on a copy of the toy library -------------------------------------------


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()
    }


def _toy_copy(run: Run, package: str | None) -> None:
    folder = run.tmp / "library"
    shutil.copytree(TOY, folder, ignore=shutil.ignore_patterns("__pycache__", "generated"))
    project = folder / "pyproject.toml"
    if package is not None:
        text = project.read_text(encoding="utf-8")
        old = next(line for line in text.splitlines() if line.startswith("package = "))
        project.write_text(text.replace(old, f'package = "{package}"', 1), encoding="utf-8")
    run.project, run.files_before = project, _snapshot(folder)
    run.package = package or ""


@given(parsers.parse('a copy of the toy library whose package is "{package}"'))
def _toy_with_package(run: Run, package: str) -> None:
    _toy_copy(run, package)


@given("a copy of the toy library whose target declares no kind")
def _toy_without_kind(run: Run) -> None:
    _toy_copy(run, None)


@when("the models are generated")
def _generate(run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    assert run.project is not None, "a project was prepared"
    run.exit_code = generate(["--project", str(run.project)])
    captured = capsys.readouterr()
    run.output = captured.out + captured.err


@then(parsers.parse('generation fails naming the package and the derived kind "{kind}"'))
def _fails_naming_package_and_kind(run: Run, kind: str) -> None:
    assert run.exit_code not in (0, None), "generation fails"
    assert run.package in run.output, f"the package is not named: {run.output}"
    assert f"a {kind} target" in run.output, f"the derived kind is not named: {run.output}"


@then(parsers.parse('generation fails naming the slot "{name}"'))
def _fails_naming_slot(run: Run, name: str) -> None:
    assert run.exit_code not in (0, None), "generation fails"
    assert name in run.output, f"the slot is not named: {run.output}"
    assert run.rule in run.output, f"the refusal is not the expected one ({run.rule}): {run.output}"


@then("no output file has changed")
def _nothing_written(run: Run) -> None:
    assert run.project is not None, "a project was prepared"
    assert _snapshot(run.project.parent) == run.files_before, "a failed run wrote a file"


@then("generation succeeds")
def _succeeds(run: Run) -> None:
    assert run.exit_code == 0, run.output


@then("it writes the same files as before")
def _same_files(run: Run) -> None:
    assert run.project is not None, "a project was prepared"
    written = run.project.parent / "domain" / "generated"
    committed = TOY / "domain" / "generated"
    names = {p.relative_to(committed).as_posix() for p in committed.rglob("*") if p.is_file()}
    names = {n for n in names if "__pycache__" not in n}
    assert names, "the committed toy output is there to compare with"
    for name in sorted(names):
        assert (written / name).read_bytes() == (committed / name).read_bytes(), f"{name} differs"


# --- a SPARQL term field ---------------------------------------------------------------------------

TERM_FIELDS = {"registry": "x", "p_kind": "x", "p_owned_by": "x"}


@given("a generated term model whose fields hold SPARQL terms")
def _term_model(run: Run) -> None:
    run.built = []


@when("it is built with a plain string")
def _plain_string(run: Run) -> None:
    try:
        RegistryTerms(**TERM_FIELDS)
    except ValidationError as error:
        run.error = error


@then("it is refused before any query text is made")
def _refused_plain(run: Run) -> None:
    assert isinstance(run.error, ValidationError), "a plain string is refused when built"


@then("it is accepted with a term made from an IRI")
def _accepted_term(run: Run) -> None:
    made = term(URIRef("https://example.org/x"))
    fields = dict.fromkeys(TERM_FIELDS, made)
    assert RegistryTerms(**fields).registry == made, "a term made by term() is accepted"


# --- a slot that defaults to an instance, or to a list ---------------------------------------------

SCHEMA_HEAD = """\
id: https://example.org/ns/groups
name: groups
title: Groups
description: A module of the groups.
prefixes: {g: "https://example.org/ns/g#", linkml: "https://w3id.org/linkml/"}
default_prefix: g
default_range: string
imports: [linkml:types]
annotations:
  module_kind: technical
classes:
"""
GROUP_CLASS = """\
  Group:
    title: Group
    description: A group of values.
    slots: [size]
"""
HOLDER_CLASS = """\
  Holder:
    title: Holder
    description: Holds a group.
    slots: [group]
"""
SLOTS = """\
slots:
  size:
    title: Size
    description: A count.
    range: integer
{size_extra}
  group:
    title: Group slot
    description: The group.
    range: {range}
{group_extra}    annotations:
      default_instance: 'true'
"""
SIZE_DEFAULT = "    ifabsent: int(3)"
SIZE_REQUIRED = "    required: true"
FAULTS = {
    "ranges over a type": {"range": "string"},
    "ranges over a class with a required slot without default": {"size_extra": SIZE_REQUIRED},
    "ranges over a class declared after its holder": {"order": "after"},
    "takes many values": {"group_extra": "    multivalued: true\n"},
}
LIST_SCHEMA = """\
  Names:
    title: Names
    description: Holds a list.
    slots: [names]
slots:
  names:
    title: Names slot
    description: The names.
    multivalued: true
    required: true
    minimum_cardinality: 1
    ifabsent: {ifabsent}
"""


def _groups_schema(
    *, range: str = "Group", size_extra: str = SIZE_DEFAULT, group_extra: str = "", order: str = ""
) -> str:
    classes = HOLDER_CLASS + GROUP_CLASS if order == "after" else GROUP_CLASS + HOLDER_CLASS
    slots = SLOTS.format(range=range, size_extra=size_extra, group_extra=group_extra)
    return SCHEMA_HEAD + classes + slots


def _project(run: Run, schema_text: str) -> None:
    """A small project of one technical schema; ``rp-generate`` writes ``generated/groups.py``."""
    folder = run.tmp / "project"
    folder.mkdir()
    (folder / "groups.yaml").write_text(schema_text, encoding="utf-8")
    (folder / "pyproject.toml").write_text(
        '[tool.rp-generate]\nschema = "groups.yaml"\npackage = "project.services.generated"\n'
        'python = "generated"\n',
        encoding="utf-8",
    )
    run.project, run.files_before = folder / "pyproject.toml", _snapshot(folder)


def _generated_module(run: Run) -> ModuleType:
    assert run.project is not None, "a project was prepared"
    path = run.project.parent / "generated" / "groups.py"
    spec = importlib.util.spec_from_file_location("groups_under_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@given(parsers.parse('a class with a "{slot}" slot that defaults to an instance of its class'))
def _holder(run: Run, slot: str) -> None:
    run.schema_text = _groups_schema()


@given("the class of the group gives a default to every one of its slots")
def _group_defaults(run: Run) -> None:
    _project(run, run.schema_text)


@when("two objects of the class are built with no value for the group")
def _two_holders(run: Run) -> None:
    assert generate(["--project", str(run.project)]) == 0, "the schema generates"
    holder = _generated_module(run).Holder
    run.built = [holder(), holder()]


@then("each holds a group with its defaults")
def _groups_hold_defaults(run: Run) -> None:
    assert [h.group.size for h in run.built] == [3, 3], "each group holds the default size"


@then("the two groups are distinct")
def _groups_distinct(run: Run) -> None:
    first, second = run.built
    assert first.group is not second.group, "each object has a group of its own"


@given(parsers.parse("a slot that defaults to an instance but {fault}"))
def _faulty_slot(run: Run, fault: str) -> None:
    run.rule = "[default_instance]"
    _project(run, _groups_schema(**FAULTS[fault]))


@given(parsers.parse('a slot that takes many values and defaults to "{names}"'))
def _list_default(run: Run, names: str) -> None:
    _project(run, SCHEMA_HEAD + LIST_SCHEMA.format(ifabsent=f"string({names})"))


@given("a slot that takes many values and whose default is the number 3")
def _list_number(run: Run) -> None:
    run.rule = "multivalued"
    _project(run, SCHEMA_HEAD + LIST_SCHEMA.format(ifabsent="int(3)"))


@when("two objects are built with no value for the slot")
def _two_names(run: Run) -> None:
    assert generate(["--project", str(run.project)]) == 0, "the schema generates"
    names = _generated_module(run).Names
    run.built = [names(), names()]


@then(parsers.parse("each holds the list {first}, {second}"))
def _lists_hold(run: Run, first: str, second: str) -> None:
    expected = [first.strip('"'), second.strip('"')]
    assert [o.names for o in run.built] == [expected, expected], "each holds the list"


@then("the two lists are distinct")
def _lists_distinct(run: Run) -> None:
    first, second = run.built
    first.names.append("EdDSA")
    assert "EdDSA" not in second.names, "each object has a list of its own"


# --- the settings -----------------------------------------------------------------------------------

STORE_URL = "http://fuseki.test:3030"
HTTP_CLIENT_TIMEOUTS = (5.0, 30.0)


def _transport() -> httpx.MockTransport:
    return httpx.MockTransport(lambda _request: httpx.Response(200))


def _client_timeouts(store: FusekiStore, verifier: JwksTokenVerifier) -> list[tuple[float, float]]:
    async def read() -> list[tuple[float, float]]:
        async with store, verifier:
            return [
                (adapter.client.timeout.connect, adapter.client.timeout.read)
                for adapter in (store, verifier)
            ]

    return asyncio.run(read())


def _adapters(http: HttpSettings | None) -> tuple[FusekiStore, JwksTokenVerifier]:
    extra = {} if http is None else {"http": http}
    store = FusekiStore(STORE_URL, "u", "p", transport=_transport(), **extra)
    verifier = JwksTokenVerifier(ISSUER, "aud", "roles", transport=_transport(), **extra)
    return store, verifier


@when("a consumer builds its adapters and the service kit without settings")
def _built_without_settings(run: Run) -> None:
    run.toolkit = ToyService().kit.toolkit
    run.built = _client_timeouts(*_adapters(None))


@then(parsers.parse('the {group} value "{slot}" is {value}'))
def _default_value(run: Run, group: str, slot: str, value: str) -> None:
    assert run.toolkit is not None, "the service kit was built"
    assert str(getattr(getattr(run.toolkit, group), slot)) == value, f"{group}.{slot}"


@then(
    "the HTTP client of the store and of the token verifier waits 5 seconds to connect and 30 to read"
)
def _default_timeouts(run: Run) -> None:
    assert run.built == [HTTP_CLIENT_TIMEOUTS] * 2, "both clients keep the old timeouts"


@given(parsers.parse("settings with an HTTP read timeout of {seconds:d} seconds"))
def _http_settings(run: Run, seconds: int) -> None:
    run.http = ToolkitSettings(http=HttpSettings(read_timeout_seconds=seconds)).http


@when("the consumer builds its store and token verifier with its HTTP group")
def _built_with_http(run: Run) -> None:
    run.built = _client_timeouts(*_adapters(run.http))


@then(parsers.parse("both use a read timeout of {seconds:d} seconds"))
def _both_read(run: Run, seconds: int) -> None:
    assert [read for _connect, read in run.built] == [float(seconds)] * 2, (
        "both read for the set time"
    )


@when(parsers.parse('a JWKS settings group lists "{name}" among its allowed algorithms'))
def _jwks_lists(run: Run, name: str) -> None:
    try:
        jwks = JwksSettings(allowed_algorithms=[name, "RS256"])
        run.built = [JwksTokenVerifier(ISSUER, "aud", "roles", transport=_transport(), jwks=jwks)]
    except ValidationError as error:
        run.error = error


@then("the settings are refused")
def _settings_refused(run: Run) -> None:
    assert isinstance(run.error, ValidationError), "the settings model refuses the list"


@then("no token verifier is built")
def _no_verifier(run: Run) -> None:
    assert isinstance(run.error, ValidationError), "the settings model refused the list"
    assert run.built == [], "the refusal comes before any verifier"


@given(parsers.parse('a JWKS settings group that lists "{name}" among its allowed algorithms'))
def _jwks_group_named(run: Run, name: str) -> None:
    run.schema_text = name


@when("the settings are built")
def _settings_built(run: Run) -> None:
    run.jwks = JwksSettings(allowed_algorithms=[run.schema_text, "RS256"])


@then("the settings are accepted")
def _settings_accepted(run: Run) -> None:
    assert run.jwks is not None, "the settings were built"
    assert run.jwks.allowed_algorithms == [run.schema_text, "RS256"], "the list is kept as given"


@then(parsers.parse('building the token verifier from them fails naming "{name}"'))
def _verifier_fails(run: Run, name: str) -> None:
    with pytest.raises(ValueError, match=name):
        JwksTokenVerifier(ISSUER, "aud", "roles", jwks=run.jwks)


# --- the environment --------------------------------------------------------------------------------


@given(parsers.parse('the environment variable "{name}" is "{value}"'))
def _variable(run: Run, name: str, value: str) -> None:
    run.environ[name] = value


@when("the consumer reads the toolkit settings from the environment")
def _read_environment(run: Run) -> None:
    run.toolkit = settings_from_env(ToolkitSettings, environ=run.environ)


@then(parsers.parse("the HTTP read timeout is {seconds:d} seconds"))
def _read_timeout(run: Run, seconds: int) -> None:
    assert run.toolkit is not None, "the settings were read"
    assert run.toolkit.http.read_timeout_seconds == float(seconds), "the variable is used"


@then("every other value is its default")
def _others_default(run: Run) -> None:
    assert run.toolkit is not None, "the settings were read"
    expected = ToolkitSettings().model_dump()
    expected["http"]["read_timeout_seconds"] = run.toolkit.http.read_timeout_seconds
    assert run.toolkit.model_dump() == expected, "only the one value differs"


IMPORT_PROBE = (
    "import sys, rdf_persistence;"
    "assert 'pydantic_settings' not in sys.modules, 'the settings library was loaded';"
    "assert 'rdf_persistence.api.entrypoints' not in sys.modules, 'the entrypoints were loaded'"
)


@when("the toolkit is imported")
def _import_toolkit(run: Run) -> None:
    run.probe = subprocess.run(
        [sys.executable, "-c", IMPORT_PROBE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin", **run.environ},
    )


@then("the import succeeds")
def _import_succeeds(run: Run) -> None:
    assert run.probe is not None, "the toolkit was imported"
    assert run.probe.returncode == 0, run.probe.stderr


@then("nothing has read the variable")
def _nothing_read(run: Run) -> None:
    assert run.probe is not None, "the toolkit was imported"
    assert run.probe.stderr == "", "a read of the invalid value would have been reported"
