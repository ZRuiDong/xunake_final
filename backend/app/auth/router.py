from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

from app.auth.dependencies import get_current_user
from app.auth.schema import PasswordChangeRequest, TokenResponse
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.security import (
    hash_password,
    verify_password,
    create_token,
    pwd_context,
)
from app.auth.rate_limit import login_limiter

_DUMMY_PASSWORD_HASH = hash_password("invalid-account-timing-padding")


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)



@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    login_limiter.check(data.username)
    user = db.query(User).filter(
        User.username == data.username
    ).first()


    if not user:
        verify_password(data.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=401,
            detail="invalid username or password"
        )


    if not verify_password(
        data.password,
        user.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="invalid username or password"
        )


    login_limiter.success(data.username)
    if pwd_context.needs_update(user.password_hash):
        # A concurrent admin reset must not be overwritten by legacy rehashing.
        changed = db.query(User).filter(
            User.id == user.id, User.password_hash == user.password_hash,
            User.token_version == user.token_version,
        ).update({User.password_hash: hash_password(data.password)}, synchronize_session=False)
        if not changed:
            db.rollback()
            raise HTTPException(401, "account changed; sign in again")
        db.commit()
        db.refresh(user)
    token = create_token(user)


    return {

        "access_token": token,

        "token_type": "bearer",

        "role": user.role,

        "must_change_password": user.must_change_password,

    }


@router.post("/change-password")
def change_password(
    data: PasswordChangeRequest,
    username=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.username == username
    ).with_for_update().first()

    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="old password is incorrect")

    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="new password must be different from the old password",
        )

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return {
        "message": "password changed",
        "access_token": create_token(user),
        "must_change_password": False,
    }
