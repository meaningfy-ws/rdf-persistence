"""TC-2 (domain-values-and-fixes, #301): the toy's technical module holds the value classes it imports.

The toy generates ``loan_checks`` (a value module) into its own domain package, and
``loan_checks_response`` (a technical module) into a services package that imports it.
"""

from tests.fixtures.library.domain.generated.values import loan_checks
from tests.fixtures.library.services.generated import loan_checks_response
from tests.fixtures.library.services.generated.loan_checks_response import LoanChecksResponse


def test_the_technical_module_imports_the_value_class_it_does_not_regenerate() -> None:
    assert loan_checks_response.LoanCheck is loan_checks.LoanCheck, (
        "the technical module holds its own copy of LoanCheck, so isinstance would fail"
    )
    assert "LoanCheck" not in vars(LoanChecksResponse), "the response declares the class itself"


def test_a_response_holds_value_instances_of_the_one_class() -> None:
    check = loan_checks.LoanCheck(
        check_status=loan_checks.LoanStatus.OVERDUE,
        check_findings=[loan_checks.LoanFinding(finding_code="late")],
    )
    response = LoanChecksResponse(checks=[check])
    assert isinstance(response.checks[0], loan_checks.LoanCheck), "the held check is not the class"
    assert response.checks[0].check_findings[0].finding_code == "late", "the finding was lost"
