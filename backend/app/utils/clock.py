import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
APP_TIMEZONE = timezone(timedelta(hours=float(os.getenv("APP_UTC_OFFSET_HOURS", "8"))))


def app_now():
    """Existing naive database timestamps use application time, not server time."""
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)
