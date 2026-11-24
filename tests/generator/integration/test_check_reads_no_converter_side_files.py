"""``rp-generate --check`` reads the schemas only, never the roles or the workflow files (task 1.8).

The how-to of the UML converter tells the modeller that the service, not the generator, reads
``<root>.roles.yaml`` and ``workflows/*.workflow.yaml``; this pins it.
"""

from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main

from .generated_project import module, root_class, write_project


def test_a_check_passes_beside_a_roles_file_and_a_workflow_file_that_are_garbage(
    project: Path,  # the fixture of this folder's conftest.py
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject = write_project(project, {"app_main": module("app_main", root_class("Book"))})
    (project / "app.roles.yaml").write_bytes(b"\xff - not a list: [")
    (project / "workflows").mkdir()
    (project / "workflows" / "loan.workflow.yaml").write_bytes(b"\xff - not a mapping: [")

    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err
    code = main(["--check", "--project", str(pyproject)])

    assert code == 0, f"the check read a file it should not: {capsys.readouterr().err}"
