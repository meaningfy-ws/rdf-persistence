"""The start-up report of grants: what a tenant's grants name that no role definition covers (grant-roles D-5, DEC-5).

A role is defined by the roles file, and a stored grant can outlive its definition. The report warns, once
per tenant, of the roles that are no longer defined and of a tenant that no grant administers (one with no
grants included). It reads every access record once and never raises: a start-up must not stop for a report.
"""

import logging

from rdf_persistence.access.domain.generated.rp_access import Grant
from rdf_persistence.access.services.access import AccessRules
from rdf_persistence.core.domain.exceptions import PersistenceError
from rdf_persistence.core.services.generated.rp_core_services import LogContext
from rdf_persistence.core.services.telemetry import log_extra
from rdf_persistence.tenancy.services.tenancy import Tenancy

log = logging.getLogger(__name__)

STEP = "check-grants"


async def report_grants(tenancy: Tenancy, rules: AccessRules) -> None:
    """Warn of the undefined roles and of the tenants no grant administers; never raises.

    A failed read (the store is down, a record does not decode: ``StoredDataInvalid`` is a
    ``PersistenceError``) is logged at ERROR and ends the report. The tenant of a record comes from
    ``tenancy``, so the level of a grant follows the tenancy's IRI policy.
    """
    try:
        records = await tenancy.access_records()
    except PersistenceError as error:
        log.error(
            "the grants could not be checked",
            exc_info=error,
            extra=log_extra(LogContext(step=STEP)),
        )
        return
    for record in records:
        _report_tenant(rules, tenancy.tenant_of(record), record.grants or [])


def _report_tenant(rules: AccessRules, tenant: str, grants: list[Grant]) -> None:
    """Warn of the undefined roles of one tenant's ``grants``, and when none of them administers it."""
    undefined = rules.undefined_roles(grants, tenant)
    if undefined:
        log.warning(
            "grants name undefined roles",
            extra=log_extra(
                LogContext(
                    step=STEP,
                    tenant_id=tenant,
                    undefined_roles=[f"{level.value}:{role}" for level, role in undefined],
                )
            ),
        )
    if not rules.administered(grants, tenant):
        log.warning(
            "no grant administers the tenant",
            extra=log_extra(LogContext(step=STEP, tenant_id=tenant)),
        )
