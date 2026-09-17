from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.period import Period
from app.models.selection import Selection
from app.utils.clock import app_now, APP_TIMEZONE


def period_status(start_time: datetime, end_time: datetime, now: datetime | None = None):
    """Return the status implied by a period's configured local times."""
    now = now or app_now()

    if now < start_time:
        return "WAITING"

    if now < end_time:
        return "ACTIVE"

    return "CLOSED"


def finalize_period_selections(period_id: int, db: Session):
    selections = db.query(Selection).filter(
        Selection.period_id == period_id,
        Selection.status.in_(["SELECTED", "WAITING"]),
    ).populate_existing().all()

    finalized_count = 0
    for selection in selections:
        if selection.status == "SELECTED":
            selection.status = "FINAL"
            finalized_count += 1
        else:
            selection.status = "REJECTED"
            selection.queue_position = None

    return finalized_count


def sync_period_statuses(db: Session, commit: bool = True):
    """Synchronize persisted period states with the current time."""
    now = app_now()
    changed = False

    # Only transitions need an exclusive lock. Ordinary selections hold SHARE
    # locks, so closing waits for all in-flight writes without serializing them.
    periods = db.query(Period).filter(
        Period.status != "CLOSED",
        or_(Period.end_time <= now,
            (Period.status == "WAITING") & (Period.start_time <= now)),
    ).order_by(Period.id).populate_existing().with_for_update().all()

    for period in periods:
        status = period_status(period.start_time, period.end_time, app_now())

        if period.status == status:
            continue

        period.status = status
        changed = True

        if status == "CLOSED":
            finalize_period_selections(period.id, db)
            period.finalized_time = now

    if commit and periods:
        db.commit()

    return changed


def get_active_period(db: Session):
    sync_period_statuses(db)

    return db.query(Period).filter(
        Period.status == "ACTIVE"
    ).first()


def lock_period_for_write(db: Session, period_id: int, shared: bool = False):
    """Acquire the stage gate before student/course locks, then refresh its state."""
    sync_period_statuses(db)
    period = db.query(Period).filter(Period.id == period_id).populate_existing().with_for_update(read=shared).first()
    if period and period.status != "CLOSED":
        actual_status = period_status(period.start_time, period.end_time)
        if actual_status != period.status:
            if shared:
                db.rollback()
                return lock_period_for_write(db, period_id, shared=True)
            period.status = actual_status
            if actual_status == "CLOSED":
                finalize_period_selections(period.id, db)
                period.finalized_time = app_now()
            db.flush()
    return period


def get_locked_active_period(db: Session):
    """Lock and revalidate the active period for a selection write."""
    sync_period_statuses(db)
    period = db.query(Period).filter(
        Period.status == "ACTIVE"
    ).populate_existing().with_for_update(read=True).first()
    if not period:
        return None

    actual_status = period_status(period.start_time, period.end_time)
    if actual_status == "ACTIVE":
        return period

    # Never upgrade simultaneous SHARE locks: that can deadlock at the deadline.
    # No mutation has happened at this point; release and synchronize exclusively.
    db.rollback()
    sync_period_statuses(db)
    return None
