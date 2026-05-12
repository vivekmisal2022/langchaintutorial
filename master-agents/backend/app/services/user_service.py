"""User service for JWT token handling and user info extraction."""
import base64
import json
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)


@dataclass
class UserInfo:
    """User information extracted from JWT token."""
    user_id: str  # Unique user identifier (sub claim)
    email: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    full_name: Optional[str] = None
    user_name: Optional[str] = None  # SAP user name
    initials: Optional[str] = None  # Computed initials for UI display

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "full_name": self.full_name,
            "user_name": self.user_name,
            "initials": self.initials,
        }


def decode_jwt_payload(token: str) -> Optional[dict]:
    """
    Decode JWT token payload without verification.

    Note: The App Router already validates the token, so we just need to decode it.

    Args:
        token: JWT token string (with or without 'Bearer ' prefix)

    Returns:
        Decoded payload as dictionary, or None if decoding fails
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # JWT has 3 parts: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            logger.warning("Invalid JWT format: expected 3 parts")
            return None

        # Decode the payload (second part)
        # Add padding if needed for base64 decoding
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        return payload

    except Exception as e:
        logger.error(f"Error decoding JWT payload: {e}")
        return None


def extract_user_info(request: Request) -> Optional[UserInfo]:
    """
    Extract user information from the request's Authorization header.

    Args:
        request: FastAPI request object

    Returns:
        UserInfo object or None if no valid token found
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        logger.debug("No Authorization header found")
        return None

    payload = decode_jwt_payload(auth_header)
    if not payload:
        return None

    # Log the full payload for debugging (only in debug mode)
    logger.debug(f"JWT payload claims: {list(payload.keys())}")

    # Extract user ID - prefer user_uuid (SAP I-number) for consistency
    user_id = (
        payload.get("user_uuid")  # SAP I-number (e.g., I340544)
        or payload.get("sub")
        or payload.get("user_id")
    )
    if not user_id:
        logger.warning("No user ID found in JWT token")
        return None

    # Extract name information
    # SAP XSUAA typically uses these claims
    given_name = payload.get("given_name") or payload.get("givenName")
    family_name = payload.get("family_name") or payload.get("familyName")
    full_name = payload.get("name")
    email = payload.get("email")
    user_name = payload.get("user_name") or payload.get("userName")

    # Compute initials
    initials = _compute_initials(given_name, family_name, full_name, email, user_name)

    return UserInfo(
        user_id=user_id,
        email=email,
        given_name=given_name,
        family_name=family_name,
        full_name=full_name,
        user_name=user_name,
        initials=initials,
    )


def _compute_initials(
    given_name: Optional[str],
    family_name: Optional[str],
    full_name: Optional[str],
    email: Optional[str],
    user_name: Optional[str],
) -> str:
    """Compute user initials for UI display."""
    # Try given + family name first
    if given_name and family_name:
        return (given_name[0] + family_name[0]).upper()

    # Try full name
    if full_name:
        parts = full_name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        elif len(parts) == 1 and len(parts[0]) >= 2:
            return parts[0][:2].upper()

    # Try email
    if email:
        local_part = email.split("@")[0]
        if "." in local_part:
            parts = local_part.split(".")
            return (parts[0][0] + parts[-1][0]).upper()
        elif len(local_part) >= 2:
            return local_part[:2].upper()

    # Try user_name
    if user_name and len(user_name) >= 2:
        return user_name[:2].upper()

    return "??"


def get_user_id_from_request(request: Request) -> str:
    """
    Get user ID from request, falling back to 'anonymous' if not authenticated.

    Args:
        request: FastAPI request object

    Returns:
        User ID string
    """
    user_info = extract_user_info(request)
    if user_info:
        return user_info.user_id
    return "anonymous"


def get_raw_jwt_payload(request: Request) -> Optional[dict]:
    """
    Get the raw JWT payload for debugging purposes.

    Args:
        request: FastAPI request object

    Returns:
        Raw JWT payload dictionary or None
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    return decode_jwt_payload(auth_header)
