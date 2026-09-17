from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.course import Course
from app.models.period import Period
from app.models.selection import Selection
from app.models.student import Student
from app.models.user import User
from app.utils.period import app_now, get_active_period, get_locked_active_period, sync_period_statuses
from app.utils.selection import (
    MAX_COURSES_PER_STUDENT,
    calculate_ranking,
    update_selection_status,
)


router = APIRouter(prefix="/student", tags=["student"])
BLOCKING_SELECTION_STATUSES = ["WAITING", "SELECTED", "FINAL"]


def get_student_by_username(username: str, db: Session, lock: bool = False):
    query = db.query(Student, User).join(User).filter(User.username == username)
    if lock:
        query = query.populate_existing().with_for_update(of=Student)

    record = query.first()
    if not record:
        raise HTTPException(status_code=403, detail="student only")

    student, user = record
    if user.must_change_password:
        raise HTTPException(
            status_code=428,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "message": "password change required",
            },
        )

    return student


@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    username=Depends(get_current_user),
):
    sync_period_statuses(db)
    student = get_student_by_username(username, db)
    selection_query = db.query(Selection, Course, Period).join(
        Course,
        Selection.course_id == Course.id,
    ).outerjoin(
        Period,
        Selection.period_id == Period.id,
    ).filter(
        Selection.student_id == student.id
    )
    records = selection_query.filter(
        Selection.status.in_(BLOCKING_SELECTION_STATUSES)
    ).order_by(Selection.selected_time.desc(), Selection.id.desc()).all()
    if not records:
        rejected_record = selection_query.filter(
            Selection.status == "REJECTED"
        ).order_by(Selection.selected_time.desc(), Selection.id.desc()).first()
        records = [rejected_record] if rejected_record else []

    selections = []
    for record in records:
        selection_item, course, period = record
        selections.append({
            "course_id": course.id,
            "course_name": course.name,
            "period_id": selection_item.period_id,
            "period_name": period.name if period else None,
            "period_status": period.status if period else None,
            "status": selection_item.status,
        })

    return {
        "name": student.name,
        "student_no": student.student_no,
        "selection": selections[0] if selections else None,
        "selections": selections,
    }


@router.get("/courses")
def get_courses(
    db: Session = Depends(get_db),
    username=Depends(get_current_user),
):
    student = get_student_by_username(username, db)
    period = get_active_period(db)

    if not period:
        return []

    active_selection_count = db.query(Selection).filter(
        Selection.student_id == student.id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).count()
    courses = db.query(Course).filter(
        Course.period_id == period.id
    ).order_by(Course.id).all()
    selected_counts = dict(db.query(Selection.course_id, func.count(Selection.id)).filter(
        Selection.period_id == period.id,
        Selection.status.in_(["SELECTED", "FINAL"]),
    ).group_by(Selection.course_id).all())
    my_selections = {item.course_id: item for item in db.query(Selection).filter(
        Selection.student_id == student.id,
        Selection.period_id == period.id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).all()}
    result = []

    for course in courses:
        selected_count = selected_counts.get(course.id, 0)
        my_selection = my_selections.get(course.id)

        result.append({
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "instructor": course.instructor,
            "location": course.location,
            "schedule": course.schedule,
            "capacity": course.capacity,
            "selected_count": selected_count,
            "status": course.status,
            "period_id": period.id,
            "period_name": period.name,
            "period_active": True,
            "can_select": (
                active_selection_count < MAX_COURSES_PER_STUDENT
                and my_selection is None
                and course.status == "OPEN"
            ),
            "is_selected": my_selection is not None,
            "selection_status": my_selection.status if my_selection else None,
        })

    return result


@router.post("/select/{course_id}")
def select_course(
    course_id: int,
    db: Session = Depends(get_db),
    username=Depends(get_current_user),
):
    period = get_locked_active_period(db)
    if not period:
        raise HTTPException(status_code=400, detail="selection period is not active")

    student = get_student_by_username(username, db, lock=True)
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.period_id == period.id,
    ).with_for_update().first()

    if not course:
        raise HTTPException(
            status_code=404,
            detail="course is not available in the active period",
        )
    if course.status != "OPEN":
        raise HTTPException(status_code=400, detail="course is closed")

    existing_for_course = db.query(Selection).filter(
        Selection.student_id == student.id,
        Selection.course_id == course_id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).first()
    if existing_for_course:
        return {"message": "selected", "status": existing_for_course.status}

    active_selection_count = db.query(Selection).filter(
        Selection.student_id == student.id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).count()
    if active_selection_count >= MAX_COURSES_PER_STUDENT:
        raise HTTPException(
            status_code=400,
            detail="student can select at most two courses",
        )

    selected_count = db.query(Selection).filter(
        Selection.course_id == course_id,
        Selection.status.in_(["SELECTED", "FINAL"]),
    ).count()
    selection = db.query(Selection).filter(
        Selection.student_id == student.id,
        Selection.period_id == period.id,
        Selection.course_id == course_id,
        Selection.status == "REJECTED",
    ).with_for_update().first()
    if selection:
        selection.course_id = course_id
        selection.selected_time = app_now()
        selection.status = "SELECTED" if selected_count < course.capacity else "WAITING"
        selection.queue_position = None
    else:
        selection = Selection(
            student_id=student.id,
            course_id=course_id,
            period_id=period.id,
            selected_time=app_now(),
            status="SELECTED" if selected_count < course.capacity else "WAITING",
        )
        db.add(selection)
    db.flush()
    update_selection_status(course_id, db, commit=False)
    db.commit()
    db.refresh(selection)

    return {"message": "selected", "status": selection.status}


@router.get("/course/{course_id}/rank")
def get_rank(
    course_id: int,
    db: Session = Depends(get_db),
    username=Depends(get_current_user),
):
    sync_period_statuses(db)
    student = get_student_by_username(username, db)
    selection = db.query(Selection).filter(
        Selection.student_id == student.id,
        Selection.course_id == course_id,
        Selection.status != "REJECTED",
    ).first()
    if not selection:
        raise HTTPException(status_code=404, detail="selection not found")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="course not found")

    ranking = calculate_ranking(course_id, db)
    for index, item in enumerate(ranking, start=1):
        if item.Selection.student_id == student.id:
            return {
                "student_id": student.id,
                "rank": index,
                "capacity": course.capacity,
                "status": item.Selection.status,
            }

    raise HTTPException(status_code=404, detail="selection not found")


@router.delete("/cancel/{course_id}")
def cancel_course(
    course_id: int,
    db: Session = Depends(get_db),
    username=Depends(get_current_user),
):
    period = get_locked_active_period(db)
    if not period:
        raise HTTPException(status_code=400, detail="selection period is not active")

    student = get_student_by_username(username, db, lock=True)
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.period_id == period.id,
    ).with_for_update().first()
    if not course:
        raise HTTPException(status_code=404, detail="course is not available")
    selection = db.query(Selection).filter(
        Selection.course_id == course_id,
        Selection.student_id == student.id,
        Selection.period_id == period.id,
    ).first()
    if not selection:
        return {"message": "cancel success"}
    if selection.status == "FINAL":
        raise HTTPException(status_code=400, detail="course already finalized")

    db.delete(selection)
    db.flush()
    update_selection_status(course_id, db, commit=False)
    db.commit()
    return {"message": "cancel success"}
