import hmac
from typing import Optional
from Apps.ai.core.config import get_settings
from Apps.ai.core.exceptions import AuthenticationError


def validate_service_api_key(provided_key: Optional[str]) -> bool:
    """
    Validate an incoming API key against the configured service API key
    using constant-time comparison to prevent timing attacks.
    """
    if not provided_key:
        return False

    settings = get_settings()
    expected_key = settings.SERVICE_API_KEY
    return hmac.compare_digest(provided_key.encode("utf-8"), expected_key.encode("utf-8"))


def verify_api_key_or_raise(provided_key: Optional[str]) -> None:
    """
    Verify the provided API key or raise AuthenticationError.
    """
    if not validate_service_api_key(provided_key):
        raise AuthenticationError("Invalid or missing X-API-Key header")
