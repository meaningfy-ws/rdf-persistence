"""The generated classes of the metamodel, read by the tests of the toolkit and of the generator."""

import importlib
import pkgutil

from pydantic import BaseModel

# The metamodel's classes generate into one package per theme (domain-model-per-theme DEC-1).
METAMODEL_PACKAGE = tuple(
    f"rdf_persistence.{theme}.domain.generated"
    for theme in ("core", "access", "provenance", "files", "collaboration")
)


def generated_models(package: str | tuple[str, ...]) -> list[type[BaseModel]]:
    """The pydantic classes each module of a generated package (or of each of several) declares itself."""
    if isinstance(package, tuple):
        return [model for one in package for model in generated_models(one)]
    root = importlib.import_module(package)
    modules = [
        importlib.import_module(f"{package}.{info.name}")
        for info in pkgutil.iter_modules(root.__path__)
    ]
    return [
        value
        for module in modules
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == module.__name__
        and value.__name__ not in {"ConfiguredBaseModel", "LinkMLMeta"}
    ]
