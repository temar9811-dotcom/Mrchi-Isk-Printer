# FILE: app/esi/pkce.py
# VERSION: 1.0.0

import base64
import hashlib
import secrets


def _base64url_encode(data: bytes) -> str:
    """
    Encode bytes to base64url without padding.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def generate_pkce() -> tuple[str, str]:
    """
    Generate a PKCE code verifier and S256 code challenge.
    """
    verifier = _base64url_encode(secrets.token_bytes(32))
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = _base64url_encode(digest)
    return verifier, challenge


def generate_state() -> str:
    """
    Generate a random state string for CSRF protection.
    """
    return secrets.token_urlsafe(16)