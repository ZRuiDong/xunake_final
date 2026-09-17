import os

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from passlib.context import CryptContext

from jose import jwt




# ==============================
# 加载环境变量
# ==============================

load_dotenv()




# ==============================
# JWT配置
# ==============================

SECRET_KEY = os.getenv(
    "SECRET_KEY"
)



ALGORITHM = os.getenv(
    "ALGORITHM",
    "HS256"
)



ACCESS_TOKEN_EXPIRE_HOURS = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_HOURS",
        12
    )
)




if not SECRET_KEY:

    raise RuntimeError(
        "SECRET_KEY is not configured"
    )





# ==============================
# 密码加密
# ==============================

pwd_context = CryptContext(

    schemes=["bcrypt_sha256", "bcrypt"],

    deprecated="auto"

)





# ==============================
# 密码哈希
# ==============================

def hash_password(password):

    return pwd_context.hash(
        password
    )





# ==============================
# 密码验证
# ==============================

def verify_password(
    plain,
    hashed
):

    return pwd_context.verify(

        plain,

        hashed

    )





# ==============================
# 创建JWT Token
# ==============================

def create_token(user):


    payload = {


        "sub": user.username,

        "uid": user.id,

        "ver": user.token_version,


        "exp":
            datetime.now(timezone.utc)
            +
            timedelta(
                hours=ACCESS_TOKEN_EXPIRE_HOURS
            )

    }



    return jwt.encode(

        payload,

        SECRET_KEY,

        algorithm=ALGORITHM

    )
