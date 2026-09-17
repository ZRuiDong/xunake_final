from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine


if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("database connect success")
    except SQLAlchemyError as error:
        # Avoid exposing credentials or connection details through exceptions.
        print(f"database connection failed: {type(error).__name__}")
        raise SystemExit(1)
