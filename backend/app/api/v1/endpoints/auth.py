import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.service import (
    AuthError,
    authenticate_user,
    is_refresh_token_revoked,
    issue_tokens,
    logout_user,
    register_user,
    request_password_reset,
    reset_password,
    send_verification_email,
    verify_email,
)
from app.core.rate_limit import limiter
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserPublic,
    UserRegister,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Auth endpoints get tighter, dedicated limits on top of the app-wide
# default — these are the highest-value targets for credential-stuffing
# and registration-spam bots, so they don't just inherit the generic limit.
_AUTH_ABUSE_LIMIT = "10/minute"
# Password reset / verification-resend are lower-frequency, legitimate-use
# actions than login/register, but still worth a dedicated (looser) limit
# so they can't be used to spam a victim's inbox.
_EMAIL_ACTION_LIMIT = "5/minute"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_AUTH_ABUSE_LIMIT)
def register(request: Request, payload: UserRegister, db: Session = Depends(get_db)):
    try:
        user = register_user(db, payload)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    access_token, refresh_token = issue_tokens(user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_AUTH_ABUSE_LIMIT)
def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    try:
        user = authenticate_user(db, payload)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    access_token, refresh_token = issue_tokens(user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    logout_user(db, payload.refresh_token)
    return MessageResponse(message="Logged out")


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    token_data = decode_token(payload.refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    jti = token_data.get("jti")
    if not jti or is_refresh_token_revoked(db, jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.get(User, uuid.UUID(token_data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    access_token, refresh_token = issue_tokens(user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(_EMAIL_ACTION_LIMIT)
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    request_password_reset(db, payload.email)
    # Always the same response, regardless of whether the email exists —
    # see request_password_reset's docstring.
    return MessageResponse(message="If an account exists for that email, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit(_EMAIL_ACTION_LIMIT)
def reset_password_endpoint(
    request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)
):
    try:
        reset_password(db, payload.token, payload.new_password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return MessageResponse(message="Your password has been reset. You can now sign in.")


@router.post("/verify-email", response_model=MessageResponse)
def verify_email_endpoint(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        verify_email(db, payload.token)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return MessageResponse(message="Your email has been verified.")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit(_EMAIL_ACTION_LIMIT)
def resend_verification(
    request: Request, payload: ResendVerificationRequest, db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == payload.email).first()
    # Same "always succeeds" principle as forgot-password — don't reveal
    # whether the email exists or is already verified.
    if user and not user.is_email_verified:
        send_verification_email(db, user)
    return MessageResponse(message="If an account exists for that email, a verification link has been sent.")
