import os
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError as PoolTimeout
from app.database import engine

from fastapi.middleware.cors import CORSMiddleware


from app.auth.router import router as auth_router

from app.admin.router import router as admin_router

from app.course.router import router as course_router

from app.student.router import router as student_router



app = FastAPI(
    title="Course Selection System"
)


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
async def database_busy(request, error):
    # Do not leak SQL/connection credentials into HTTP responses.
    logging.getLogger(__name__).warning("Database temporarily unavailable (%s)", type(error).__name__)
    return JSONResponse(status_code=503, content={"detail": "server busy; refresh selection results before retrying"},
                        headers={"Retry-After": "2"})


@app.exception_handler(IntegrityError)
async def database_conflict(request, error):
    return JSONResponse(status_code=409, content={"detail": "data conflict; refresh and retry"})


@app.get("/health", include_in_schema=False)
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}


cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]



# ==============================
# CORS 跨域配置
# ==============================

app.add_middleware(

    CORSMiddleware,

    allow_origins=cors_origins,

    allow_credentials=True,

    allow_methods=[

        "*"

    ],

    allow_headers=[

        "*"

    ]

)



# ==============================
# 注册路由
# ==============================


app.include_router(
    auth_router
)


app.include_router(
    admin_router
)


app.include_router(
    course_router
)


app.include_router(
    student_router
)



# ==============================
# 测试接口
# ==============================

@app.get("/")
def root():

    return {

        "message":
        "course selection system running"

    }
