"""The model guard and the file guard of ``testkit.assert_models_generated`` (PD-28)."""

from pathlib import Path

import pytest

from rdf_persistence.testkit.guards import assert_models_generated

PKG = "fakepkg"
DOMAIN_FILE = f"{PKG}/domain/thing.py"

# (id, module source, expected class name)
MODEL_CASES = [
    (
        "pydantic-from",
        "from pydantic import BaseModel\nclass Thing(BaseModel):\n    x: int\n",
        "Thing",
    ),
    (
        "pydantic-module-alias",
        "import pydantic as p\nclass Thing(p.BaseModel):\n    x: int\n",
        "Thing",
    ),
    (
        "pydantic-name-alias",
        "from pydantic import BaseModel as BM\nclass Thing(BM):\n    pass\n",
        "Thing",
    ),
    (
        "pydantic-plain-import",
        "import pydantic\nclass Thing(pydantic.BaseModel):\n    pass\n",
        "Thing",
    ),
    (
        "pydantic-generic",
        "from typing import Generic, TypeVar\nfrom pydantic import BaseModel\nT = TypeVar('T')\nclass Thing(BaseModel, Generic[T]):\n    pass\n",
        "Thing",
    ),
    (
        "rpmodel-absolute",
        "from rdf_persistence.domain.base import RpModel\nclass Thing(RpModel):\n    pass\n",
        "Thing",
    ),
    (
        "rpmodel-module",
        "from rdf_persistence.domain import base\nclass Thing(base.RpModel):\n    pass\n",
        "Thing",
    ),
    ("enum", "from enum import Enum\nclass Thing(Enum):\n    A = 1\n", "Thing"),
    ("enum-alias", "from enum import Enum as E\nclass Thing(E):\n    A = 1\n", "Thing"),
    ("strenum", "import enum\nclass Thing(enum.StrEnum):\n    A = 'a'\n", "Thing"),
    ("intenum", "from enum import IntEnum\nclass Thing(IntEnum):\n    A = 1\n", "Thing"),
    ("typeddict", "from typing import TypedDict\nclass Thing(TypedDict):\n    x: int\n", "Thing"),
    ("namedtuple", "import typing\nclass Thing(typing.NamedTuple):\n    x: int\n", "Thing"),
    (
        "typing-extensions",
        "from typing_extensions import TypedDict\nclass Thing(TypedDict):\n    x: int\n",
        "Thing",
    ),
    (
        "dataclass-bare",
        "from dataclasses import dataclass\n@dataclass\nclass Thing:\n    x: int\n",
        "Thing",
    ),
    (
        "dataclass-call",
        "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Thing:\n    x: int\n",
        "Thing",
    ),
    (
        "dataclass-module",
        "import dataclasses\n@dataclasses.dataclass(slots=True)\nclass Thing:\n    x: int\n",
        "Thing",
    ),
    (
        "dataclass-alias",
        "from dataclasses import dataclass as dc\n@dc\nclass Thing:\n    x: int\n",
        "Thing",
    ),
    (
        "generated-subclass",
        "from fakepkg.domain.generated.m import Grant\nclass Thing(Grant):\n    pass\n",
        "Thing",
    ),
    (
        "generated-subclass-alias",
        "from fakepkg.domain.generated.m import Grant as G\nclass Thing(G):\n    pass\n",
        "Thing",
    ),
    (
        "generated-subclass-module",
        "from fakepkg.domain.generated import m\nclass Thing(m.Grant):\n    pass\n",
        "Thing",
    ),
    (
        "generated-subclass-relative",
        "from .generated.m import Grant\nclass Thing(Grant):\n    pass\n",
        "Thing",
    ),
    (
        "generated-subclass-top-level",
        "from fakepkg import Grant\nclass Thing(Grant):\n    pass\n",
        "Thing",
    ),
    (
        "generated-subclass-top-level-alias",
        "import fakepkg as fp\nclass Thing(fp.Grant):\n    pass\n",
        "Thing",
    ),
    (
        "nested-class",
        "from pydantic import BaseModel\ndef f():\n    class Thing(BaseModel):\n        pass\n",
        "Thing",
    ),
]

CLEAN_CASES = [
    ("plain-class", "class Thing:\n    pass\n"),
    ("exception", "class Boom(Exception):\n    pass\n"),
    (
        "exception-subclass",
        "from pydantic import ValidationError\nclass Boom(ValueError):\n    pass\n",
    ),
    ("top-level-non-generated", "from fakepkg import Plain\nclass Thing(Plain):\n    pass\n"),
    ("unrelated-basemodel", "from other import BaseModel\nclass Thing(BaseModel):\n    pass\n"),
    ("unrelated-dataclass", "from other import dataclass\n@dataclass\nclass Thing:\n    pass\n"),
    ("function-only", "def f():\n    return 1\n"),
]


def plant(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def check(root: Path, **kwargs) -> None:
    kwargs.setdefault("roots", [])
    plant(
        root,
        f"{PKG}/__init__.py",
        "from fakepkg.domain.generated.m import Grant\nfrom fakepkg.other import Plain\n",
    )
    assert_models_generated(root / PKG, **kwargs)


@pytest.mark.parametrize("layer", ["domain", "services", "entrypoints"])
@pytest.mark.parametrize(("case", "source", "name"), MODEL_CASES, ids=[c[0] for c in MODEL_CASES])
def test_hand_written_model_is_named(tmp_path, layer, case, source, name):
    plant(tmp_path, f"{PKG}/{layer}/thing.py", source)
    with pytest.raises(AssertionError) as err:
        check(tmp_path)
    message = str(err.value)
    assert f"{PKG}/{layer}/thing.py:" in message, "the file is named with a line number"
    assert name in message, "the class is named"


def test_violation_line_number_points_at_the_class(tmp_path):
    plant(
        tmp_path,
        DOMAIN_FILE,
        "from pydantic import BaseModel\n\n\nclass Thing(BaseModel):\n    pass\n",
    )
    with pytest.raises(AssertionError, match=r"thing\.py:4: .*Thing"):
        check(tmp_path)


@pytest.mark.parametrize(("case", "source"), CLEAN_CASES, ids=[c[0] for c in CLEAN_CASES])
def test_clean_module_passes(tmp_path, case, source):
    plant(tmp_path, DOMAIN_FILE, source)
    assert check(tmp_path) is None, "no violation, nothing returned"


def test_every_violation_is_listed_one_per_line(tmp_path):
    plant(
        tmp_path, f"{PKG}/domain/a.py", "from pydantic import BaseModel\nclass A(BaseModel): ...\n"
    )
    plant(tmp_path, f"{PKG}/services/b.py", "from enum import Enum\nclass B(Enum): ...\n")
    with pytest.raises(AssertionError) as err:
        check(tmp_path)
    lines = [
        line
        for line in str(err.value).splitlines()
        if "thing" not in line and (" A" in line or " B" in line)
    ]
    assert len(lines) == 2, "one line per violation"


def test_generated_folder_is_ignored(tmp_path):
    plant(
        tmp_path,
        f"{PKG}/domain/generated/m.py",
        "from pydantic import BaseModel\nclass G(BaseModel): ...\n",
    )
    plant(
        tmp_path,
        f"{PKG}/services/generated/deep/m.py",
        "from enum import Enum\nclass G(Enum): ...\n",
    )
    assert check(tmp_path) is None, "classes under generated/ are not scanned"


def test_other_layers_are_not_scanned(tmp_path):
    plant(
        tmp_path,
        f"{PKG}/adapters/m.py",
        "from pydantic import BaseModel\nclass Config(BaseModel): ...\n",
    )
    assert check(tmp_path) is None, "only domain, services and entrypoints are scanned"


def test_missing_layers_are_fine(tmp_path):
    (tmp_path / PKG).mkdir()
    assert check(tmp_path) is None, "a package with none of the three layers passes"


def test_rpmodel_in_domain_base_is_allowed_by_default(tmp_path):
    plant(
        tmp_path,
        "rdf_persistence/domain/base.py",
        "from pydantic import BaseModel\nclass RpModel(BaseModel): ...\n",
    )
    assert assert_models_generated(tmp_path / "rdf_persistence", roots=[]) is None, (
        "the one default exception"
    )


def test_rpmodel_elsewhere_is_not_allowed(tmp_path):
    plant(
        tmp_path,
        f"{PKG}/domain/other.py",
        "from pydantic import BaseModel\nclass RpModel(BaseModel): ...\n",
    )
    with pytest.raises(AssertionError, match="RpModel"):
        check(tmp_path)


def test_allow_exempts_the_named_class_only(tmp_path):
    plant(
        tmp_path,
        DOMAIN_FILE,
        "from pydantic import BaseModel\nclass Keep(BaseModel): ...\nclass Drop(BaseModel): ...\n",
    )
    with pytest.raises(AssertionError) as err:
        check(tmp_path, allow=[f"{DOMAIN_FILE}:Keep"])
    assert "Drop" in str(err.value), "the unlisted class is still reported"
    assert "Keep" not in str(err.value), "the allowed class is not reported"


def test_package_given_as_import_name():
    assert assert_models_generated("json", roots=[]) is None, (
        "an import name resolves to the package root"
    )


def test_relative_import_of_rpmodel_is_resolved(tmp_path):
    (tmp_path / PKG / "domain").mkdir(parents=True)
    plant(
        tmp_path, f"{PKG}/domain/other.py", "from .base import RpModel\nclass Thing(RpModel): ...\n"
    )
    # the fake package is not rdf_persistence, so the relative name resolves to fakepkg.domain.base
    assert check(tmp_path) is None, "fakepkg.domain.base.RpModel is not the toolkit's RpModel"


def test_relative_import_inside_toolkit_package_is_resolved(tmp_path):
    root = tmp_path / "rdf_persistence"
    plant(
        tmp_path,
        "rdf_persistence/domain/other.py",
        "from .base import RpModel\nclass Thing(RpModel): ...\n",
    )
    with pytest.raises(AssertionError, match="Thing"):
        assert_models_generated(root, roots=[])


FILE_BAD = [
    "x.shacl.ttl",
    "my_shapes.ttl",
    "shapes.ttl",
    "a.context.jsonld",
    "context.jsonld",
    "A.frame.jsonld",
    "a.schema.json",
    "openapi.json",
    "openapi-v2.yaml",
    "types.ts",
    "deep/er/types.ts",
]
FILE_OK = [
    "data.ttl",
    "notes.json",
    "openapi.md",
    "a.test.ts",
    "a.spec.ts",
    "x.py",
]


def run_files(tmp_path: Path, **kwargs) -> None:
    assert_models_generated(tmp_path / PKG, roots=[tmp_path / "area"], **kwargs)


@pytest.mark.parametrize("name", FILE_BAD)
def test_forbidden_file_is_named(tmp_path, name):
    plant(tmp_path, f"area/{name}", "")
    with pytest.raises(AssertionError, match=name.split("/")[-1].replace(".", r"\.")):
        run_files(tmp_path)


@pytest.mark.parametrize("name", FILE_OK)
def test_allowed_file_passes(tmp_path, name):
    plant(tmp_path, f"area/{name}", "")
    assert run_files(tmp_path) is None, "not a generated artefact"


@pytest.mark.parametrize("name", FILE_BAD)
def test_forbidden_file_inside_generated_passes(tmp_path, name):
    plant(tmp_path, f"area/sub/generated/{name}", "")
    assert run_files(tmp_path) is None, "generated/ holds generated artefacts"


def test_exempt_folder_passes(tmp_path):
    plant(tmp_path, "area/fixtures/bad.shacl.ttl", "")
    assert run_files(tmp_path, exempt=[tmp_path / "area" / "fixtures"]) is None, (
        "exempt folder is skipped"
    )


def test_exempt_does_not_cover_siblings(tmp_path):
    plant(tmp_path, "area/fixtures/bad.shacl.ttl", "")
    plant(tmp_path, "area/other/bad.shacl.ttl", "")
    with pytest.raises(AssertionError) as err:
        run_files(tmp_path, exempt=[tmp_path / "area" / "fixtures"])
    assert "other" in str(err.value), "the sibling is reported"
    assert "fixtures" not in str(err.value), "the exempt folder is not"


def test_model_and_file_violations_are_reported_together(tmp_path):
    plant(tmp_path, DOMAIN_FILE, "from pydantic import BaseModel\nclass Thing(BaseModel): ...\n")
    plant(tmp_path, "area/x.shacl.ttl", "")
    with pytest.raises(AssertionError) as err:
        run_files(tmp_path)
    assert "Thing" in str(err.value), "the model violation is listed"
    assert "x.shacl.ttl" in str(err.value), "the file violation is listed"
