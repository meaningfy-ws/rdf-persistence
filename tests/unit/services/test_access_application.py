"""``AccessRules.require_application``: who may take an action on application data (app-level-data PD-9; TC-42)."""

import pytest

from rdf_persistence import Action
from rdf_persistence.domain.exceptions import Forbidden
from rdf_persistence.domain.generated.rp_access import RoleDefinition, RoleLevel
from rdf_persistence.services.access import AccessRules
from tests.toy import caller

DEFINITIONS = [
    RoleDefinition(role="admin", level=RoleLevel.SYSTEM, actions=[Action.READ]),
    RoleDefinition(role="app-editor", level=RoleLevel.SYSTEM, actions=[Action.READ, Action.MODIFY]),
    RoleDefinition(role="writer", level=RoleLevel.SYSTEM, actions=[Action.MODIFY]),
    RoleDefinition(role="librarian", level=RoleLevel.TENANT, actions=list(Action)),
]
# What a caller with these global roles may do: its system permits, and read when it has any other action.
ALLOWED = {
    (): set(),
    ("admin",): {Action.READ},
    ("app-editor",): {Action.READ, Action.MODIFY},
    ("writer",): {Action.READ, Action.MODIFY},
    (
        "librarian",
    ): set(),  # a tenant role is granted in a tenant; a token's global role never reaches it
    ("ghost",): set(),  # no definition
    ("admin", "writer"): {Action.READ, Action.MODIFY},
}
CASES = [
    pytest.param(roles, action, action in allowed, id=f"{'+'.join(roles) or 'none'}-{action.value}")
    for roles, allowed in ALLOWED.items()
    for action in Action
]


@pytest.mark.parametrize(("roles", "action", "allowed"), CASES)
def test_tc42_the_action_is_allowed_exactly_when_the_global_roles_permit_it(roles, action, allowed):
    rules = AccessRules(DEFINITIONS)
    if allowed:
        assert rules.require_application(caller(*roles), action) is None, (
            f"{roles} may {action.value}"
        )
        return
    with pytest.raises(Forbidden, match=f"{action.value} is not permitted on application data"):
        rules.require_application(caller(*roles), action)
