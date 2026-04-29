"""Authentication router for FinSight.

Endpoints
---------
- ``POST /auth/register``  — create a free account; system generates the password
- ``POST /auth/login``     — exchange credentials for HttpOnly JWT cookies
- ``POST /auth/refresh``   — rotate the access token using the refresh token cookie
- ``POST /auth/logout``    — revoke the refresh token and clear both cookies

Cookie configuration
--------------------
All auth cookies are ``HttpOnly``, ``Secure``, ``SameSite=Lax``:
- ``HttpOnly``   — prevents JavaScript from reading the token (XSS protection).
- ``Secure``     — transmitted over HTTPS only.
- ``SameSite=Lax`` — blocks cross-site POST forgery while allowing top-level
  navigations (e.g. OAuth redirects).
"""

import hashlib
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth.jwt import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_refresh_token,
)
from auth.password import generate_secure_password, hash_password, verify_password
from database import get_db
from models import RefreshToken, User

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Request body for account registration."""

    email: EmailStr


class RegisterResponse(BaseModel):
    """Response returned on successful registration.

    The ``generated_password`` field is displayed **once** in the UI.
    It is never stored in plain text and cannot be recovered after this
    response is sent.
    """

    email: str
    generated_password: str
    message: str


class LoginRequest(BaseModel):
    """Request body for login."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Minimal login confirmation — tokens are set as HttpOnly cookies."""

    email: str
    role: str
    message: str


class RefreshResponse(BaseModel):
    """Confirmation that the access token has been rotated."""

    message: str


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

# Set COOKIE_SECURE=false in local development (HTTP). Production (HTTPS) should
# leave this unset or set it to "true" so cookies are only sent over HTTPS.
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"

_COOKIE_OPTS = dict(httponly=True, secure=_COOKIE_SECURE, samesite="lax", path="/")


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Write both auth cookies onto a response object.

    Args:
        response:      FastAPI ``Response`` (or ``JSONResponse``) to mutate.
        access_token:  Signed JWT access token string.
        refresh_token: Signed JWT refresh token string.
    """
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=15 * 60,  # 15 minutes
        **_COOKIE_OPTS,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **_COOKIE_OPTS,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Delete both auth cookies by setting max_age=0.

    Args:
        response: FastAPI ``Response`` to mutate.
    """
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def _hash_refresh_token(raw: str) -> str:
    """Return a SHA-256 hex digest of a raw refresh token for DB storage.

    Args:
        raw: The plain-text JWT refresh token string.

    Returns:
        64-character lowercase hex digest.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    """Register a new free-tier account.

    The system generates a cryptographically secure password and returns it
    **once** in this response.  The user must copy it immediately as it cannot
    be recovered.

    Args:
        body: ``RegisterRequest`` containing the user's email address.
        db:   Active database session (injected).

    Returns:
        ``RegisterResponse`` with the email and the generated password.

    Raises:
        HTTPException 409: If an account already exists for that email.
    """
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    raw_password = generate_secure_password()
    user = User(
        email=body.email,
        hashed_password=hash_password(raw_password),
        role="free",
    )
    db.add(user)
    db.commit()

    return RegisterResponse(
        email=body.email,
        generated_password=raw_password,
        message=(
            "Account created. Copy your password now — it will not be shown again."
        ),
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Authenticate and set HttpOnly JWT cookies.

    On success, sets two cookies:
    - ``access_token``  — 15-minute JWT
    - ``refresh_token`` — 7-day JWT (hash stored in DB for revocation)

    Args:
        body:     ``LoginRequest`` with email and password.
        response: FastAPI response object used to set cookies.
        db:       Active database session.

    Returns:
        ``LoginResponse`` confirming the user's email and role.

    Raises:
        HTTPException 401: If the credentials are invalid or the account is inactive.
    """
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_payload = {"sub": user.email, "role": user.role}
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token({"sub": user.email})

    # Persist a hash of the refresh token so it can be revoked on logout
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(refresh_token),
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()

    _set_auth_cookies(response, access_token, refresh_token)

    return LoginResponse(email=user.email, role=user.role, message="Login successful.")


@router.post("/refresh", response_model=RefreshResponse)
def refresh_token(
    response: Response,
    refresh_token: str = Cookie(default=None),
    db: Session = Depends(get_db),
) -> RefreshResponse:
    """Rotate the access token using a valid refresh token cookie.

    The existing refresh token is revoked and a new access token is
    issued.  The refresh token itself is reused (not rotated) to avoid
    signing out users on every page reload, but is checked against the
    DB each time to detect revocation.

    Args:
        response:      FastAPI response for setting the new access token cookie.
        refresh_token: JWT from the ``refresh_token`` HttpOnly cookie.
        db:            Active database session.

    Returns:
        ``RefreshResponse`` confirming the token was rotated.

    Raises:
        HTTPException 401: If the refresh token is missing, expired, or revoked.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
    )
    if not refresh_token:
        raise credentials_exc

    try:
        payload = decode_token(refresh_token)
        if not is_refresh_token(payload):
            raise credentials_exc
        email: str = payload.get("sub")
        if not email:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    token_hash = _hash_refresh_token(refresh_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked.is_(False),
    ).first()
    if not stored:
        raise credentials_exc

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise credentials_exc

    # Always re-read the role from the DB so that role upgrades (e.g.
    # free → paid after a Stripe payment) are reflected in the new token.
    new_access_token = create_access_token({"sub": user.email, "role": user.role})
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        max_age=15 * 60,
        **_COOKIE_OPTS,
    )

    return RefreshResponse(message="Access token refreshed.")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str = Cookie(default=None),
    db: Session = Depends(get_db),
) -> None:
    """Revoke the refresh token and clear both auth cookies.

    Silently succeeds even if the user is not currently logged in, so
    that clients can safely call logout without checking session state.

    Args:
        response:      FastAPI response for clearing cookies.
        refresh_token: JWT from the ``refresh_token`` HttpOnly cookie.
        db:            Active database session.
    """
    if refresh_token:
        token_hash = _hash_refresh_token(refresh_token)
        db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).update({"revoked": True})
        db.commit()

    _clear_auth_cookies(response)
