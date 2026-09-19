from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.security import SECRET_KEY, ALGORITHM
from app.database import SessionLocal
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


@dataclass(frozen=True)
class AuthenticatedUser:
    username: str
    role: str
    must_change_password: bool


def authenticate_token(token: str, db: Session) -> AuthenticatedUser:
    """Validate a token against the current user record.

    Keeping this database check preserves immediate token revocation after a
    password reset.  The FastAPI dependencies below deliberately use their own
    short-lived session so the connection is returned before the endpoint is
    queued in the sync worker pool.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        username = payload.get("sub")
        user_id = payload.get("uid")
        token_version = payload.get("ver")
    except JWTError as error:
        raise HTTPException(status_code=401, detail="invalid token") from error

    if username is None or user_id is None or token_version is None:
        raise HTTPException(status_code=401, detail="invalid token")

    user = db.query(User).filter(
        User.id == user_id,
        User.username == username,
        User.token_version == token_version,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="invalid token")

    return AuthenticatedUser(
        username=user.username,
        role=user.role,
        must_change_password=user.must_change_password,
    )


def _authenticate_with_short_session(token: str) -> AuthenticatedUser:
    # Do not share this session with the endpoint. Under a large burst, a
    # shared session can hold every pooled connection while endpoints are
    # still waiting for a worker thread, starving the entire application.
    db = SessionLocal()
    try:
        return authenticate_token(token, db)
    finally:
        db.close()



def get_current_user(
    token: str = Depends(oauth2_scheme),
):
    return _authenticate_with_short_session(token).username



def admin_required(
    token: str = Depends(oauth2_scheme),
):
    user = _authenticate_with_short_session(token)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="admin only")

    if user.must_change_password:
        raise HTTPException(
            status_code=428,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "message": "password change required",
            },
        )


    return user.username
