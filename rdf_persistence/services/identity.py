"""The identity port: administering the accounts of the identity provider.

Every method is async. An account is named by the provider's id (``AccountSummary.account_id``).
Signing in is not here: the provider's own flows do that (D-10), and ``TokenVerifier`` checks the
result.
"""

from typing import Protocol

from rdf_persistence.domain.generated.service.rp_service import AccountSummary


class Identity(Protocol):
    """Find, list, disable and enable accounts, and grant and remove their global roles."""

    async def find_by_email(self, email: str) -> AccountSummary:
        """The account whose email is exactly ``email``.

        Raises:
            NotFound: No account has that email.
            IdentityUnavailable: The provider is unreachable or failed.
        """
        ...

    async def list_accounts(self) -> list[AccountSummary]:
        """Every account; raises ``IdentityUnavailable`` as ``find_by_email`` does."""
        ...

    async def disable(self, account_id: str) -> None:
        """Refuse the account new tokens. Disabling a disabled account is harmless.

        Raises:
            NotFound: No such account.
            IdentityUnavailable: The provider is unreachable or failed.
        """
        ...

    async def enable(self, account_id: str) -> None:
        """Undo ``disable``; raises as ``disable`` does."""
        ...

    async def grant_global_role(self, account_id: str, role: str) -> None:
        """Give the account a global role. Granting a held role is harmless.

        Raises:
            NotFound: No such account, or the provider has no such role.
            IdentityUnavailable: The provider is unreachable or failed.
        """
        ...

    async def remove_global_role(self, account_id: str, role: str) -> None:
        """Take a global role from the account; a role it does not hold is harmless. Raises as ``disable`` does."""
        ...
