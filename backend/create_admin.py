import getpass
import os

from app.database import SessionLocal
from app.models.user import User
from app.auth.security import hash_password


if __name__ == "__main__":
    password = os.getenv("INITIAL_ADMIN_PASSWORD") or getpass.getpass("Initial admin password (at least 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Admin password must contain at least 12 characters")
    with SessionLocal() as db:
        if db.query(User).filter(User.username == "admin").first():
            raise SystemExit("Admin already exists; no password was changed")
        db.add(User(username="admin", password_hash=hash_password(password),
                    role="ADMIN", must_change_password=True))
        db.commit()
    print("admin created; password change required on first login")
