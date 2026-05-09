"""FastAPI dependency callables for authentication and RBAC.

Usage
-----
Inject into route functions via ``Depends``:

    @router.get("/protected")
    def protected_route(user: User = Depends(get_current_user)):
        ...

    @router.get("/paid-only")
    def paid_route(user: User = Depends(require_role("paid", "admin"))):
        ...

    @router.post("/search")
    def search(user: User = Depends(require_api_key_or_session)):
        ...
"""

from typing import Callable

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from auth.jwt import decode_token, is_access_token
from auth.password import hash_api_key
from database import get_db
from models import APIKey, User


def _get_user_by_email(email: str, db: Session) -> User:
    """Fetch an active user by email or raise 401.

    Args:
        email: Email address decoded from the JWT ``sub`` claim.
        db:    Active database session.

    Returns:
        The matching active ``User`` ORM instance.

    Raises:
        HTTPException 401: If no active user exists with that email.
    """
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user(
    access_token: str = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from the HttpOnly access token cookie.

    Args:
        access_token: JWT string read from the ``access_token`` HttpOnly cookie.
        db:           Active database session (injected by FastAPI).

    Returns:
        Authenticated ``User`` ORM instance.

    Raises:
        HTTPException 401: If the cookie is missing, expired, or invalid.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not access_token:
        raise credentials_exc
    try:
        payload = decode_token(access_token)
        if not is_access_token(payload):
            raise credentials_exc
        email: str = payload.get("sub")
        if not email:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    return _get_user_by_email(email, db)


def require_role(*roles: str) -> Callable:
    """Return a dependency that enforces the caller's role.

    Args:
        *roles: Allowed role strings (e.g. ``"paid"``, ``"admin"``).

    Returns:
        A FastAPI dependency callable that returns the authenticated user
        if their role is in ``roles``, or raises HTTP 403.

    Example::

        @router.get("/admin/users")
        def admin_users(user: User = Depends(require_role("admin"))):
            ...
    """

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(roles)}.",
            )
        return user

    return _check


def get_api_key_user(
    x_api_key: str = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate a request using the ``X-API-Key`` request header.

    Looks up the SHA-256 hash of the provided key in the ``api_keys``
    table and returns the owning user.

    Args:
        x_api_key: Raw API key from the ``X-API-Key`` header.
        db:        Active database session.

    Returns:
        The ``User`` associated with the valid API key.

    Raises:
        HTTPException 401: If the header is missing or the key is invalid/revoked.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header is required.",
        )
    key_hash = hash_api_key(x_api_key)
    api_key_row = (
        db.query(APIKey)
        .filter(APIKey.key_hash == key_hash, APIKey.revoked.is_(False))
        .first()
    )
    if not api_key_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
        )
    user = (
        db.query(User)
        .filter(User.id == api_key_row.user_id, User.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner is missing or deactivated.",
        )
    return user


def require_api_key_or_session(
    access_token: str = Cookie(default=None),
    x_api_key: str = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    """Accept either a session cookie or an API key for flexible auth.

    Used on endpoints that should support both the browser dashboard
    (cookie auth) and programmatic access (API key).  The caller must
    have at least the ``paid`` or ``admin`` role in either case.

    Args:
        access_token: JWT from the HttpOnly ``access_token`` cookie.
        x_api_key:    Raw key from the ``X-API-Key`` header.
        db:           Active database session.

    Returns:
        Authenticated ``User`` ORM instance with ``paid`` or ``admin`` role.

    Raises:
        HTTPException 401: If neither credential is present or valid.
        HTTPException 403: If the user's role is ``free``.
    """
    user: User | None = None

    if x_api_key:
        try:
            user = get_api_key_user(x_api_key=x_api_key, db=db)
        except HTTPException:
            pass

    if user is None and access_token:
        try:
            user = get_current_user(access_token=access_token, db=db)
        except HTTPException:
            pass

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: provide X-API-Key header or log in.",
        )

    if user.role not in ("paid", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a paid subscription.",
        )

    return user
