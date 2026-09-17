import os

from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase



# ==============================
# 加载环境变量
# ==============================

load_dotenv()



# ==============================
# 数据库配置
# ==============================

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)



if not DATABASE_URL:

    raise RuntimeError(
        "DATABASE_URL is not configured"
    )




# ==============================
# 创建数据库引擎
# ==============================

engine = create_engine(

    DATABASE_URL,

    pool_pre_ping=True,

    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),

    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),
    connect_args={"connect_timeout": 5,
                  "options": "-c lock_timeout=10000 -c statement_timeout=20000"},

)




# ==============================
# Session
# ==============================

SessionLocal = sessionmaker(

    autocommit=False,

    autoflush=False,

    bind=engine

)




# ==============================
# ORM Base
# ==============================

class Base(DeclarativeBase):

    pass




# ==============================
# FastAPI数据库依赖
# ==============================

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()
