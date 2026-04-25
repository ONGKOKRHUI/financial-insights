"""Admin user management router.

All endpoints require the ``admin`` role and are accessible only at
the hidden route ``/admin/dashboard`` in the frontend.

Endpoints
---------
- ``GET    /admin/users``        — paginated list of all users
- ``PATCH  /admin/users/{id}``   — update role or active status
- ``DELETE /admin/users/{id}``   — permanently delete a user account
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import require_role
from database import get_db
from models import APIKey, RefreshToken, User

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Response / request schemas
# ---------------------------------------------------------------------------


class AdminUserRow(BaseModel):
    """A single row in the admin user management table."""

    id: int
    email: str
    role: str
    is_active: bool
    stripe_subscription_id: Optional[str]
    has_api_key: bool
    created_at: str

    class Config:
        from_attributes = True


class AdminUsersResponse(BaseModel):
    """Paginated response for the admin user list."""

    users: List[AdminUserRow]
    total: int
    page: int
    page_size: int


class UpdateUserRequest(BaseModel):
    """Request body for PATCH /admin/users/{id}.

    All fields are optional — only provided fields are updated.
    """

    role: Optional[str] = None          # free | paid | admin
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/users", response_model=AdminUsersResponse)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> AdminUsersResponse:
    """Return a paginated list of all registered users.

    Args:
        page:      Page number (1-based).
        page_size: Number of users per page (max 100).
        _:         Admin user injected by ``require_role`` (used only for auth check).
        db:        Active database session.

    Returns:
        ``AdminUsersResponse`` with the user list and pagination metadata.
    """
    total = db.query(User).count()
    offset = (page - 1) * page_size
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    rows = []
    for u in users:
        has_api_key = (
            db.query(APIKey)
            .filter(APIKey.user_id == u.id, APIKey.revoked.is_(False))
            .first()
            is not None
        )
        rows.append(
            AdminUserRow(
                id=u.id,
                email=u.email,
                role=u.role,
                is_active=u.is_active,
                stripe_subscription_id=u.stripe_subscription_id,
                has_api_key=has_api_key,
                created_at=u.created_at.isoformat(),
            )
        )

    return AdminUsersResponse(users=rows, total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}", response_model=AdminUserRow)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> AdminUserRow:
    """Update a user's role or active status.

    Args:
        user_id: Target user's primary key.
        body:    Fields to update (all optional).
        _:       Admin user (auth check only).
        db:      Active database session.

    Returns:
        Updated ``AdminUserRow``.

    Raises:
        HTTPException 404: If no user with ``user_id`` exists.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    allowed_roles = {"free", "paid", "admin"}
    if body.role is not None:
        if body.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"role must be one of {sorted(allowed_roles)}.",
            )
        user.role = body.role

    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()
    db.refresh(user)

    has_api_key = (
        db.query(APIKey)
        .filter(APIKey.user_id == user.id, APIKey.revoked.is_(False))
        .first()
        is not None
    )
    return AdminUserRow(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        stripe_subscription_id=user.stripe_subscription_id,
        has_api_key=has_api_key,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> None:
    """Permanently delete a user account and all associated tokens/keys.

    Cascade deletes on ``refresh_tokens`` and ``api_keys`` are handled by
    the database FK constraints (``ON DELETE CASCADE``).

    Args:
        user_id: Target user's primary key.
        _:       Admin user (auth check only).
        db:      Active database session.

    Raises:
        HTTPException 404: If no user with ``user_id`` exists.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    db.delete(user)
    db.commit()
