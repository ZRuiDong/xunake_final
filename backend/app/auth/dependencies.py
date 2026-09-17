from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.security import SECRET_KEY, ALGORITHM
from app.database import get_db
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)



def get_current_user(
    token:str=Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")
        user_id = payload.get("uid")
        token_version = payload.get("ver")

    except JWTError as error:
        raise HTTPException(
            status_code=401,
            detail="invalid token"
        ) from error

    if username is None or user_id is None or token_version is None:
        raise HTTPException(status_code=401, detail="invalid token")

    user = db.query(User).filter(
        User.id == user_id,
        User.username == username,
        User.token_version == token_version,
    ).first()
    if not user:

        raise HTTPException(
            status_code=401,
            detail="invalid token"
        )

    return username



def admin_required(
    username=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.username == username,
        User.role == "ADMIN"
    ).first()

    if not user:

        raise HTTPException(
            status_code=403,
            detail="admin only"
        )

    if user.must_change_password:
        raise HTTPException(
            status_code=428,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "message": "password change required",
            },
        )


    return username
