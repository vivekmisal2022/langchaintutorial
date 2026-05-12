"""User API endpoints for authentication info and user management."""
import logging
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.user_service import (
    extract_user_info,
    get_raw_jwt_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["user"])


class UserInfoResponse(BaseModel):
    """User information response."""
    authenticated: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    full_name: Optional[str] = None
    user_name: Optional[str] = None
    initials: Optional[str] = None


class JWTDebugResponse(BaseModel):
    """JWT debug response - only for development."""
    has_token: bool
    payload: Optional[dict] = None
    headers: dict


@router.get("/user/me", response_model=UserInfoResponse)
async def get_current_user(request: Request):
    """
    Get the current authenticated user's information.

    Returns user info extracted from the JWT token provided by App Router.
    If no valid token is present, returns authenticated=False.
    """
    user_info = extract_user_info(request)

    if user_info:
        return UserInfoResponse(
            authenticated=True,
            user_id=user_info.user_id,
            email=user_info.email,
            given_name=user_info.given_name,
            family_name=user_info.family_name,
            full_name=user_info.full_name,
            user_name=user_info.user_name,
            initials=user_info.initials,
        )

    return UserInfoResponse(authenticated=False)


@router.get("/user/debug-token", response_model=JWTDebugResponse)
async def debug_jwt_token(request: Request):
    """
    Debug endpoint to inspect the JWT token.

    WARNING: This endpoint exposes token contents. Use only for debugging.
    Consider disabling in production.
    """
    # Get relevant headers
    headers = {
        "Authorization": request.headers.get("Authorization", "")[:50] + "..."
        if request.headers.get("Authorization")
        else None,
        "X-Forwarded-User": request.headers.get("X-Forwarded-User"),
        "X-Forwarded-Email": request.headers.get("X-Forwarded-Email"),
        "X-User-Info": request.headers.get("X-User-Info"),
    }

    # Filter out None values
    headers = {k: v for k, v in headers.items() if v is not None}

    # Get JWT payload
    payload = get_raw_jwt_payload(request)

    # Mask sensitive values in payload
    if payload:
        masked_payload = {}
        sensitive_keys = {"iat", "exp", "jti", "aud", "iss"}
        for key, value in payload.items():
            if key in sensitive_keys:
                masked_payload[key] = value
            elif isinstance(value, str) and len(value) > 50:
                masked_payload[key] = value[:50] + "..."
            else:
                masked_payload[key] = value
    else:
        masked_payload = None

    return JWTDebugResponse(
        has_token=payload is not None,
        payload=masked_payload,
        headers=headers,
    )
