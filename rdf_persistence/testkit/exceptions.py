"""The errors of the Zitadel testkit."""


class ProvisioningError(RuntimeError):
    """The test Zitadel refused a provisioning call or answered with something unreadable; the message holds the status, never a secret."""


class TokenRefusedError(RuntimeError):
    """Zitadel refused a token request (a disabled account, an unknown key, ...)."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"Zitadel refused the token request with {status_code}")
        self.status_code = status_code
