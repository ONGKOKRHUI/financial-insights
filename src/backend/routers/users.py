"""User profile and API key management router.

Endpoints
---------
- ``GET  /users/me``                — return the current user's profile
- ``GET  /users/me/api-key``        — return the API key prefix (paid/admin)
- ``POST /users/me/api-key/rotate`` — revoke the existing key and generate a new one
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, require_role
from auth.password import generate_api_key
from database import get_db
from models import APIKey, User

router = APIRouter(prefix="/users", tags=["users"])

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserProfile(BaseModel):
    """Public-safe user profile returned by GET /users/me."""

    id: int
    email: str
    role: str
    has_api_key: bool

    class Config:
        from_attributes = True


class APIKeyInfo(BaseModel):
    """Safe representation of an API key (prefix only — never the full key)."""

    key_prefix: str
    created_at: str
    message: str


class NewAPIKeyResponse(BaseModel):
    """Response returned when a key is created or rotated.

    ``raw_key`` is displayed **once** and never stored in plain text.
    """

    raw_key: str
    key_prefix: str
    message: str


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserProfile)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfile:
    """Return the authenticated user's profile.

    Args:
        current_user: User injected by the ``get_current_user`` dependency.
        db:           Active database session.

    Returns:
        ``UserProfile`` with id, email, role, and whether they have an API key.
    """
    has_api_key = (
        db.query(APIKey)
        .filter(APIKey.user_id == current_user.id, APIKey.revoked.is_(False))
        .first()
        is not None
    )
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        has_api_key=has_api_key,
    )


@router.get("/me/api-key", response_model=APIKeyInfo)
def get_api_key_info(
    current_user: User = Depends(require_role("paid", "admin")),
    db: Session = Depends(get_db),
) -> APIKeyInfo:
    """Return the API key prefix for the current paid/admin user.

    The full key is never returned after initial creation.  The prefix
    is safe to display so users can identify their active key.

    Args:
        current_user: Paid or admin user injected by ``require_role``.
        db:           Active database session.

    Returns:
        ``APIKeyInfo`` with the key prefix and creation timestamp.

    Raises:
        HTTPException 404: If the user does not have an active API key.
    """
    api_key = (
        db.query(APIKey)
        .filter(APIKey.user_id == current_user.id, APIKey.revoked.is_(False))
        .order_by(APIKey.created_at.desc())
        .first()
    )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active API key found. Use POST /users/me/api-key/rotate to generate one.",
        )
    return APIKeyInfo(
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at.isoformat(),
        message="API key is active.",
    )


@router.post("/me/api-key/rotate", response_model=NewAPIKeyResponse, status_code=status.HTTP_201_CREATED)
def rotate_api_key(
    current_user: User = Depends(require_role("paid", "admin")),
    db: Session = Depends(get_db),
) -> NewAPIKeyResponse:
    """Revoke the existing API key and issue a new one.

    The new raw key is returned **exactly once** — it is not stored in
    plain text.  The user must copy it immediately.

    Args:
        current_user: Paid or admin user injected by ``require_role``.
        db:           Active database session.

    Returns:
        ``NewAPIKeyResponse`` containing the full raw key (shown once).
    """
    # Revoke all existing active keys for this user
    db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.revoked.is_(False),
    ).update({"revoked": True})

    raw_key, key_hash, key_prefix = generate_api_key()
    db.add(
        APIKey(
            user_id=current_user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
        )
    )
    db.commit()

    return NewAPIKeyResponse(
        raw_key=raw_key,
        key_prefix=key_prefix,
        message="New API key generated. Copy it now — it will not be shown again.",
    )
