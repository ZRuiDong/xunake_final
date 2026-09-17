from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import admin_required
from app.course.schema import CourseCreate, CourseResponse, CourseStatusUpdate
from app.database import get_db
from app.models.course import Course
from app.models.period import Period
from app.models.selection import Selection
from app.utils.selection import update_selection_status
from app.utils.period import sync_period_statuses, lock_period_for_write
from app.utils.audit import audit_deletion


router = APIRouter(prefix="/admin/course", tags=["course"])


@router.post("/create", response_model=CourseResponse)
def create_course(
    data: CourseCreate,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    if db.query(Course).filter(Course.name == data.name).first():
        raise HTTPException(status_code=400, detail="course already exists")

    course = Course(
        name=data.name,
        description=data.description,
        instructor=data.instructor,
        location=data.location,
        schedule=data.schedule,
        capacity=data.capacity,
        status="OPEN",
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/list")
def get_courses(
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    periods = {period.id: period for period in db.query(Period).all()}
    courses = db.query(Course).order_by(Course.id).all()

    return [
        {
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "instructor": course.instructor,
            "location": course.location,
            "schedule": course.schedule,
            "capacity": course.capacity,
            "status": course.status,
            "period_id": course.period_id,
            "period_name": (
                periods[course.period_id].name
                if course.period_id in periods
                else None
            ),
        }
        for course in courses
    ]


@router.put("/{course_id}")
def update_course(
    course_id: int,
    data: CourseCreate,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    snapshot = db.query(Course).filter(Course.id == course_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="course not found")
    period_id = snapshot.period_id
    period = lock_period_for_write(db, period_id, shared=True) if period_id is not None else None
    course = db.query(Course).filter(Course.id == course_id).populate_existing().with_for_update().first()
    if not course:
        raise HTTPException(status_code=404, detail="course not found")

    duplicate = db.query(Course).filter(
        Course.name == data.name,
        Course.id != course_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="course name already exists")

    if course.period_id != period_id:
        raise HTTPException(status_code=409, detail="course period changed; please retry")

    final_count = db.query(Selection).filter(
        Selection.course_id == course_id,
        Selection.status == "FINAL",
    ).count()
    capacity_changed = data.capacity != course.capacity
    if capacity_changed and data.capacity < final_count:
        raise HTTPException(
            status_code=400,
            detail="capacity cannot be lower than the finalized student count",
        )
    if (
        period
        and period.status == "CLOSED"
        and data.capacity != course.capacity
    ):
        raise HTTPException(
            status_code=400,
            detail="capacity cannot be changed after the period closes",
        )

    course.name = data.name
    course.description = data.description
    course.instructor = data.instructor
    course.location = data.location
    course.schedule = data.schedule
    course.capacity = data.capacity
    db.flush()
    if capacity_changed and (not period or period.status != "CLOSED"):
        update_selection_status(course_id, db, commit=False)
    db.commit()

    return {"message": "course updated"}


@router.put("/{course_id}/status")
def update_course_status(
    course_id: int,
    data: CourseStatusUpdate,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    course = db.query(Course).filter(Course.id == course_id).with_for_update().first()
    if not course:
        raise HTTPException(status_code=404, detail="course not found")
    course.status = data.status
    db.commit()
    return {"message": "course status updated", "status": course.status}


@router.delete("/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    course_snapshot = db.query(Course).filter(Course.id == course_id).first()
    if not course_snapshot:
        raise HTTPException(status_code=404, detail="course not found")

    if course_snapshot.period_id is not None:
        db.query(Period).filter(
            Period.id == course_snapshot.period_id
        ).with_for_update().first()
    course = db.query(Course).filter(
        Course.id == course_id
    ).with_for_update().first()
    if not course:
        raise HTTPException(status_code=404, detail="course not found")

    selections = db.query(Selection).filter(Selection.course_id == course_id).all()
    audit_deletion(db, admin, "courses.delete", [course], selections)
    selection_deleted_count = db.query(Selection).filter(
        Selection.course_id == course_id
    ).delete(synchronize_session=False)
    db.delete(course)
    db.commit()
    return {
        "message": "course deleted",
        "selection_deleted_count": selection_deleted_count,
    }
