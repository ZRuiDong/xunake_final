import os
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin.period_schema import PeriodCourseAdd, PeriodCreate, PeriodUpdate
from app.admin.schema import (
    BulkDeleteRequest,
    StudentCreate,
    StudentPasswordReset,
    StudentUpdate,
)
from app.admin.selection_export import (
    build_course_selection_workbook,
    build_period_selection_workbook,
)
from app.admin.student_import import (
    StudentImportValidationError,
    build_student_template,
    parse_student_workbook,
)
from app.auth.dependencies import admin_required
from app.auth.security import hash_password
from app.database import get_db
from app.models.course import Course
from app.models.period import Period
from app.models.selection import Selection
from app.models.student import Student
from app.models.user import User
from app.utils.period import (
    app_now,
    finalize_period_selections,
    period_status,
    sync_period_statuses,
    lock_period_for_write,
)
from app.utils.selection import (
    MAX_COURSES_PER_STUDENT,
    calculate_ranking,
    update_selection_status,
)
from app.utils.audit import audit_deletion


router = APIRouter(prefix="/admin", tags=["admin"])

DEFAULT_STUDENT_PASSWORD = os.getenv("DEFAULT_STUDENT_PASSWORD", "123456")
MAX_IMPORT_FILE_SIZE = 5 * 1024 * 1024
BLOCKING_SELECTION_STATUSES = ["WAITING", "SELECTED", "FINAL"]


def lock_period_schedule(db: Session):
    """Serialize period creation/reopening in PostgreSQL."""
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(20260825)"))


def serialize_period(period: Period, course_count: int | None = None):
    result = {
        "id": period.id,
        "name": period.name,
        "start_time": period.start_time,
        "end_time": period.end_time,
        "status": period.status,
        "finalized_time": period.finalized_time,
    }

    if course_count is not None:
        result["course_count"] = course_count

    return result


def serialize_course(course: Course, period: Period | None, selected_count: int):
    return {
        "id": course.id,
        "name": course.name,
        "description": course.description,
        "instructor": course.instructor,
        "location": course.location,
        "schedule": course.schedule,
        "capacity": course.capacity,
        "status": course.status,
        "selected_count": selected_count,
        "period_id": course.period_id,
        "period_name": period.name if period else None,
        "period_status": period.status if period else None,
    }


def student_query(db: Session, keyword: str | None = None):
    query = db.query(Student)
    normalized_keyword = keyword.strip() if keyword else ""
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(or_(
            Student.student_no.ilike(pattern),
            Student.name.ilike(pattern),
        ))
    return query


def course_query(db: Session, keyword: str | None = None):
    query = db.query(Course)
    normalized_keyword = keyword.strip() if keyword else ""
    if normalized_keyword:
        query = query.filter(Course.name.ilike(f"%{normalized_keyword}%"))
    return query


def serialize_student(db: Session, student: Student):
    selection_records = db.query(Selection, Course).join(
        Course,
        Selection.course_id == Course.id,
    ).filter(
        Selection.student_id == student.id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).order_by(Selection.selected_time, Selection.id).all()
    selected_courses = [
        {
            "id": course.id,
            "name": course.name,
            "status": selection.status,
        }
        for selection, course in selection_records
    ]
    first_course = selected_courses[0] if selected_courses else None
    return {
        "id": student.id,
        "student_no": student.student_no,
        "name": student.name,
        "weight": student.weight,
        "selected_course_id": first_course["id"] if first_course else None,
        "selected_course_name": first_course["name"] if first_course else None,
        "selection_status": first_course["status"] if first_course else None,
        "selected_courses": selected_courses,
        "selected_course_names": [course["name"] for course in selected_courses],
    }


@router.post("/student/create")
def create_student(
    data: StudentCreate,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    if db.query(Student).filter(Student.student_no == data.student_no).first():
        raise HTTPException(status_code=400, detail="student already exists")

    if db.query(User).filter(User.username == data.student_no).first():
        raise HTTPException(status_code=400, detail="username already exists")

    user = User(
        username=data.student_no,
        password_hash=hash_password(data.password),
        role="STUDENT",
        must_change_password=False,
    )
    db.add(user)
    db.flush()

    student = Student(
        user_id=user.id,
        student_no=data.student_no,
        name=data.name,
        weight=data.weight,
    )
    db.add(student)
    db.commit()

    return {"message": "student created", "student_no": data.student_no}


@router.get("/students/import-template")
def download_student_import_template(
    admin=Depends(admin_required),
):
    content = build_student_template()
    return StreamingResponse(
        BytesIO(content),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": "attachment; filename=student_import_template.xlsx"
        },
    )


@router.post("/students/import")
async def import_students(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="only .xlsx files are supported")

    content = await file.read(MAX_IMPORT_FILE_SIZE + 1)
    await file.close()
    if len(content) > MAX_IMPORT_FILE_SIZE:
        raise HTTPException(status_code=400, detail="file cannot exceed 5 MB")

    try:
        records = parse_student_workbook(content)
    except StudentImportValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "student import validation failed",
                "errors": error.errors,
            },
        ) from error

    student_numbers = [record.student_no for record in records]
    existing_students = {
        item.student_no
        for item in db.query(Student).filter(
            Student.student_no.in_(student_numbers)
        ).all()
    }
    existing_users = {
        item.username
        for item in db.query(User).filter(
            User.username.in_(student_numbers)
        ).all()
    }
    duplicate_errors = [
        f"第 {record.row_number} 行：学号 {record.student_no} 已存在"
        for record in records
        if record.student_no in existing_students or record.student_no in existing_users
    ]
    if duplicate_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "student import validation failed",
                "errors": duplicate_errors,
            },
        )

    password_hash = hash_password(DEFAULT_STUDENT_PASSWORD)
    users = [
        User(
            username=record.student_no,
            password_hash=password_hash,
            role="STUDENT",
            must_change_password=True,
        )
        for record in records
    ]

    try:
        db.add_all(users)
        db.flush()
        db.add_all([
            Student(
                user_id=user.id,
                student_no=record.student_no,
                name=record.name,
                weight=record.weight,
            )
            for user, record in zip(users, records)
        ])
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="student data changed during import; please retry",
        ) from error

    return {
        "message": "students imported",
        "imported_count": len(records),
        "default_password": DEFAULT_STUDENT_PASSWORD,
    }


@router.get("/students")
def get_students(
    keyword: str | None = None,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    students = student_query(db, keyword).order_by(Student.student_no).all()
    return [serialize_student(db, student) for student in students]


@router.get("/students/page")
def get_students_page(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    query = student_query(db, keyword)
    total = query.count()
    students = query.order_by(Student.student_no).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "items": [serialize_student(db, student) for student in students],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/students/available")
def get_available_students(
    keyword: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    active_selection_count = db.query(func.count(Selection.id)).filter(
        Selection.student_id == Student.id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).correlate(Student).scalar_subquery()
    query = student_query(db, keyword).filter(
        active_selection_count < MAX_COURSES_PER_STUDENT
    )
    students = query.order_by(Student.student_no).limit(limit).all()
    return [
        {
            "id": student.id,
            "student_no": student.student_no,
            "name": student.name,
            "weight": student.weight,
        }
        for student in students
    ]


@router.post("/students/bulk-delete")
def bulk_delete_students(
    data: BulkDeleteRequest,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    db.query(Period).order_by(Period.id).populate_existing().with_for_update().all()
    sync_period_statuses(db, commit=False)
    db.flush()
    query = student_query(db, data.keyword) if data.select_all else db.query(Student)

    if data.select_all:
        if data.excluded_ids:
            query = query.filter(~Student.id.in_(data.excluded_ids))
    else:
        query = query.filter(Student.id.in_(list(set(data.ids))))

    students = query.with_for_update().all()
    student_ids = [student.id for student in students]
    user_ids = [student.user_id for student in students]

    if not student_ids:
        return {
            "deleted_count": 0,
            "selection_deleted_count": 0,
        }

    affected_selections = db.query(Selection).filter(
        Selection.student_id.in_(student_ids)
    ).all()
    affected_course_ids = sorted({item.course_id for item in affected_selections})
    if affected_course_ids:
        db.query(Course).filter(
            Course.id.in_(affected_course_ids)
        ).order_by(Course.id).with_for_update().all()

    audit_deletion(db, admin, "students.bulk_delete", students, affected_selections)

    selection_deleted_count = db.query(Selection).filter(
        Selection.student_id.in_(student_ids)
    ).delete(synchronize_session=False)
    db.query(Student).filter(
        Student.id.in_(student_ids)
    ).delete(synchronize_session=False)
    db.query(User).filter(
        User.id.in_(user_ids)
    ).delete(synchronize_session=False)

    course_periods = {
        course.id: course.period_id
        for course in db.query(Course).filter(Course.id.in_(affected_course_ids)).all()
    }
    period_statuses = {
        period.id: period.status
        for period in db.query(Period).filter(
            Period.id.in_(set(course_periods.values()))
        ).all()
    }
    for course_id in affected_course_ids:
        if period_statuses.get(course_periods.get(course_id)) != "CLOSED":
            update_selection_status(course_id, db, commit=False)
    db.commit()

    return {
        "deleted_count": len(student_ids),
        "selection_deleted_count": selection_deleted_count,
    }


@router.put("/student/{student_id}/password")
def reset_student_password(
    student_id: int,
    data: StudentPasswordReset,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="student not found")

    user = db.query(User).filter(
        User.id == student.user_id
    ).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="student account not found")

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = True
    user.token_version += 1
    db.commit()
    return {"message": "student password reset"}


@router.put("/student/{student_id}")
def update_student(
    student_id: int,
    data: StudentUpdate,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    # Weight affects all of this student's courses. Take stage gates before
    # reading their choices, including choices added by an in-flight request.
    locked_periods = {
        period.id: period for period in db.query(Period).order_by(Period.id)
        .populate_existing().with_for_update().all()
    }
    sync_period_statuses(db, commit=False)
    db.flush()
    student_snapshot = db.query(Student).filter(Student.id == student_id).first()
    if not student_snapshot:
        raise HTTPException(status_code=404, detail="student not found")

    selection_snapshots = db.query(Selection).filter(
        Selection.student_id == student_id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).order_by(Selection.course_id).all()
    student = db.query(Student).filter(
        Student.id == student_id
    ).with_for_update().first()
    if not student:
        raise HTTPException(status_code=404, detail="student not found")

    duplicate_student = db.query(Student).filter(
        Student.student_no == data.student_no,
        Student.id != student_id,
    ).first()
    duplicate_user = db.query(User).filter(
        User.username == data.student_no,
        User.id != student.user_id,
    ).first()
    if duplicate_student or duplicate_user:
        raise HTTPException(status_code=400, detail="student number already exists")

    user = db.query(User).filter(User.id == student.user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="student account not found")

    course_ids = sorted({item.course_id for item in selection_snapshots})
    if course_ids:
        db.query(Course).filter(Course.id.in_(course_ids)).order_by(
            Course.id
        ).with_for_update().all()
    selections = db.query(Selection).filter(
        Selection.student_id == student.id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).order_by(Selection.course_id).with_for_update().all()
    old_weight = student.weight
    student.student_no = data.student_no
    student.name = data.name
    student.weight = data.weight
    user.username = data.student_no
    if old_weight != data.weight:
        for selection in selections:
            period = locked_periods.get(selection.period_id)
            if not period or period.status != "CLOSED":
                update_selection_status(selection.course_id, db, commit=False)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="student data changed during update; please retry",
        ) from error

    return {"message": "student updated"}


@router.get("/periods")
def get_periods(
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    periods = db.query(Period).order_by(Period.id.desc()).all()

    return [
        serialize_period(
            period,
            db.query(Course).filter(Course.period_id == period.id).count(),
        )
        for period in periods
    ]


@router.get("/period/{period_id}")
def get_period_detail(
    period_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    period = db.query(Period).filter(Period.id == period_id).first()

    if not period:
        raise HTTPException(status_code=404, detail="period not found")

    courses = db.query(Course).filter(
        Course.period_id == period_id
    ).order_by(Course.id).all()

    course_items = []
    for course in courses:
        selected_count = db.query(Selection).filter(
            Selection.course_id == course.id,
            Selection.status.in_(["SELECTED", "FINAL"]),
        ).count()
        total_count = db.query(Selection).filter(
            Selection.course_id == course.id
        ).count()
        item = serialize_course(course, period, selected_count)
        item["total_count"] = total_count
        item["over_capacity"] = selected_count > course.capacity
        course_items.append(item)

    return {
        "period": serialize_period(period, len(courses)),
        "courses": course_items,
    }


@router.get("/period/{period_id}/export")
def export_period_selections(
    period_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="period not found")

    courses = db.query(Course).filter(
        Course.period_id == period_id
    ).order_by(Course.id).all()
    rankings = {
        course.id: calculate_ranking(course.id, db, include_rejected=True)
        for course in courses
    }
    content = build_period_selection_workbook(period, courses, rankings)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="period_selection_{period.id}.xlsx"'
            )
        },
    )


@router.get("/courses")
def get_courses(
    keyword: str | None = None,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    periods = {period.id: period for period in db.query(Period).all()}
    courses = course_query(db, keyword).order_by(Course.id).all()
    result = []

    for course in courses:
        selected_count = db.query(Selection).filter(
            Selection.course_id == course.id,
            Selection.status.in_(["SELECTED", "FINAL"]),
        ).count()
        result.append(
            serialize_course(course, periods.get(course.period_id), selected_count)
        )

    return result


@router.get("/courses/page")
def get_courses_page(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    periods = {period.id: period for period in db.query(Period).all()}
    query = course_query(db, keyword)
    total = query.count()
    courses = query.order_by(Course.id).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    items = []

    for course in courses:
        selected_count = db.query(Selection).filter(
            Selection.course_id == course.id,
            Selection.status.in_(["SELECTED", "FINAL"]),
        ).count()
        items.append(
            serialize_course(course, periods.get(course.period_id), selected_count)
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/courses/unassigned")
def get_unassigned_courses(
    keyword: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    courses = course_query(db, keyword).filter(
        Course.period_id.is_(None)
    ).order_by(Course.id).limit(limit).all()
    return [
        {"id": course.id, "name": course.name}
        for course in courses
    ]


@router.post("/courses/bulk-delete")
def bulk_delete_courses(
    data: BulkDeleteRequest,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    db.query(Period).order_by(Period.id).populate_existing().with_for_update().all()
    sync_period_statuses(db, commit=False)
    db.flush()
    query = course_query(db, data.keyword) if data.select_all else db.query(Course)

    if data.select_all:
        if data.excluded_ids:
            query = query.filter(~Course.id.in_(data.excluded_ids))
    else:
        query = query.filter(Course.id.in_(list(set(data.ids))))

    courses = query.with_for_update().all()
    course_ids = [course.id for course in courses]

    if not course_ids:
        return {
            "deleted_count": 0,
            "selection_deleted_count": 0,
        }

    selections = db.query(Selection).filter(Selection.course_id.in_(course_ids)).all()
    audit_deletion(db, admin, "courses.bulk_delete", courses, selections)
    selection_deleted_count = db.query(Selection).filter(
        Selection.course_id.in_(course_ids)
    ).delete(synchronize_session=False)
    db.query(Course).filter(
        Course.id.in_(course_ids)
    ).delete(synchronize_session=False)
    db.commit()

    return {
        "deleted_count": len(course_ids),
        "selection_deleted_count": selection_deleted_count,
    }


@router.post("/period/create")
def create_period(
    data: PeriodCreate,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    now = app_now()
    if data.end_time < now:
        raise HTTPException(status_code=400, detail="end time cannot be earlier than now")

    lock_period_schedule(db)
    sync_period_statuses(db, commit=False)
    db.flush()

    open_period = db.query(Period).filter(
        Period.status.in_(["WAITING", "ACTIVE"])
    ).first()
    if open_period:
        raise HTTPException(
            status_code=400,
            detail="another period is waiting or active",
        )

    course_ids = list(dict.fromkeys(data.course_ids))
    courses = db.query(Course).filter(Course.id.in_(course_ids)).with_for_update().all()

    if len(courses) != len(course_ids):
        raise HTTPException(status_code=404, detail="one or more courses not found")

    assigned = [course.name for course in courses if course.period_id is not None]
    if assigned:
        raise HTTPException(
            status_code=400,
            detail=f"courses already assigned: {', '.join(assigned)}",
        )

    now = app_now()
    if data.end_time < now:
        raise HTTPException(status_code=400, detail="end time cannot be earlier than now")
    new_period = Period(
        name=data.name,
        start_time=data.start_time,
        end_time=data.end_time,
        status=period_status(data.start_time, data.end_time, now),
    )
    db.add(new_period)
    db.flush()

    for course in courses:
        course.period_id = new_period.id
        db.query(Selection).filter(
            Selection.course_id == course.id,
            Selection.period_id.is_(None),
        ).update({Selection.period_id: new_period.id}, synchronize_session=False)

    db.commit()
    db.refresh(new_period)

    return {"message": "period created", "id": new_period.id}


@router.put("/period/{period_id}")
def update_period(
    period_id: int,
    data: PeriodUpdate,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    now = app_now()
    if data.end_time < now:
        raise HTTPException(status_code=400, detail="end time cannot be earlier than now")

    lock_period_schedule(db)
    sync_period_statuses(db, commit=False)
    db.flush()
    period = db.query(Period).filter(Period.id == period_id).with_for_update().first()

    if not period:
        raise HTTPException(status_code=404, detail="period not found")

    previous_status = period.status
    now = app_now()
    if data.end_time < now:
        raise HTTPException(status_code=400, detail="end time cannot be earlier than now")
    new_status = period_status(data.start_time, data.end_time, now)
    if new_status != "CLOSED":
        conflict = db.query(Period).filter(
            Period.id != period_id,
            Period.status.in_(["WAITING", "ACTIVE"]),
        ).first()
        if conflict:
            raise HTTPException(
                status_code=400,
                detail="another period is waiting or active",
            )

    period.name = data.name
    period.start_time = data.start_time
    period.end_time = data.end_time
    period.status = new_status
    period.finalized_time = None

    if new_status == "CLOSED":
        finalize_period_selections(period.id, db)
        period.finalized_time = now
    elif previous_status == "CLOSED":
        student_ids = [row[0] for row in db.query(Selection.student_id).filter(
            Selection.period_id == period.id,
            Selection.status == "REJECTED",
        ).distinct().all()]
        db.query(Student).filter(Student.id.in_(student_ids)).order_by(
            Student.id
        ).populate_existing().with_for_update().all()
        active_counts = {
            student_id: count
            for student_id, count in db.query(
                Selection.student_id,
                func.count(Selection.id),
            ).filter(
                Selection.status.in_(BLOCKING_SELECTION_STATUSES),
            ).group_by(Selection.student_id).all()
        }
        rejected = db.query(Selection).filter(
            Selection.period_id == period.id,
            Selection.status == "REJECTED",
        ).order_by(
            Selection.student_id,
            Selection.selected_time,
            Selection.id,
        ).with_for_update().all()
        for selection in rejected:
            current_count = active_counts.get(selection.student_id, 0)
            if current_count < MAX_COURSES_PER_STUDENT:
                selection.status = "WAITING"
                active_counts[selection.student_id] = current_count + 1
        courses = db.query(Course).filter(
            Course.period_id == period.id
        ).order_by(Course.id).with_for_update().all()
        for course in courses:
            update_selection_status(course.id, db, commit=False)

    db.commit()
    return {
        "message": "period updated",
        "status": period.status,
        "reopened": previous_status == "CLOSED" and new_status != "CLOSED",
    }


@router.post("/period/{period_id}/courses")
def add_period_courses(
    period_id: int,
    data: PeriodCourseAdd,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    period = lock_period_for_write(db, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="period not found")
    if period.status == "CLOSED":
        raise HTTPException(
            status_code=400,
            detail="courses cannot be added after the period closes",
        )

    course_ids = list(dict.fromkeys(data.course_ids))
    courses = db.query(Course).filter(
        Course.id.in_(course_ids)
    ).with_for_update().all()
    if len(courses) != len(course_ids):
        raise HTTPException(status_code=404, detail="one or more courses not found")

    assigned = [course.name for course in courses if course.period_id is not None]
    if assigned:
        raise HTTPException(
            status_code=400,
            detail=f"courses already assigned: {', '.join(assigned)}",
        )

    for course in courses:
        course.period_id = period.id
        db.query(Selection).filter(
            Selection.course_id == course.id,
            Selection.period_id.is_(None),
        ).update({Selection.period_id: period.id}, synchronize_session=False)

    db.commit()
    return {"message": "courses added", "count": len(courses)}


@router.delete("/period/{period_id}/courses/{course_id}")
def remove_period_course(
    period_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    period = lock_period_for_write(db, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="period not found")
    if period.status != "WAITING":
        raise HTTPException(
            status_code=400,
            detail="courses can only be changed before the period starts",
        )

    course = db.query(Course).filter(
        Course.id == course_id,
        Course.period_id == period_id,
    ).with_for_update().first()
    if not course:
        raise HTTPException(status_code=404, detail="course not found in period")
    if db.query(Selection).filter(Selection.course_id == course_id).first():
        raise HTTPException(
            status_code=400,
            detail="course already has selection records",
        )

    course.period_id = None
    db.commit()
    return {"message": "course removed from period"}


@router.post("/period/finalize")
def finalize_period(
    period_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    period = db.query(Period).filter(Period.id == period_id).populate_existing().with_for_update().first()

    if not period:
        raise HTTPException(status_code=404, detail="period not found")

    if period.status == "CLOSED":
        raise HTTPException(status_code=400, detail="period already closed")

    count = finalize_period_selections(period.id, db)
    period.status = "CLOSED"
    period.finalized_time = app_now()
    db.commit()

    return {
        "message": "finalized",
        "count": count,
        "time": period.finalized_time,
    }


@router.get("/course/{course_id}/students")
def get_course_students(
    course_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="course not found")

    ranking = calculate_ranking(course_id, db, include_rejected=True)
    students = []
    for rank, item in enumerate(ranking, start=1):
        students.append({
            "student_id": item.Student.id,
            "student_no": item.Student.student_no,
            "name": item.Student.name,
            "weight": item.Student.weight,
            "status": item.Selection.status,
            "rank": None if item.Selection.status == "REJECTED" else rank,
            "selected_time": item.Selection.selected_time,
        })

    selected_count = sum(
        1 for item in ranking if item.Selection.status in ["SELECTED", "FINAL"]
    )
    return {
        "course": course.name,
        "capacity": course.capacity,
        "selected_count": selected_count,
        "over_capacity": selected_count > course.capacity,
        "students": students,
    }


@router.get("/course/{course_id}/students/export")
def export_course_selections(
    course_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="course not found")

    period = None
    if course.period_id is not None:
        period = db.query(Period).filter(Period.id == course.period_id).first()
    content = build_course_selection_workbook(
        period,
        course,
        calculate_ranking(course.id, db, include_rejected=True),
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="course_selection_{course.id}.xlsx"'
            )
        },
    )


@router.post("/course/{course_id}/add_student")
def admin_add_student(
    course_id: int,
    student_id: int,
    allow_over_capacity: bool = False,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    course_snapshot = db.query(Course).filter(Course.id == course_id).first()
    if not course_snapshot:
        raise HTTPException(status_code=404, detail="course not found")
    if course_snapshot.period_id is None:
        raise HTTPException(status_code=400, detail="course is not assigned to a period")

    period = lock_period_for_write(db, course_snapshot.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="period not found")

    student = db.query(Student).filter(Student.id == student_id).with_for_update().first()
    if not student:
        raise HTTPException(status_code=404, detail="student not found")

    course = db.query(Course).filter(Course.id == course_id).with_for_update().first()
    if not course:
        raise HTTPException(status_code=404, detail="course not found")
    if course.period_id != period.id:
        raise HTTPException(status_code=409, detail="course period changed; please retry")

    active_selections = db.query(Selection).filter(
        Selection.student_id == student_id,
        Selection.status.in_(BLOCKING_SELECTION_STATUSES),
    ).order_by(Selection.id).with_for_update().all()
    existing = next(
        (item for item in active_selections if item.course_id == course_id),
        None,
    )
    period_record = db.query(Selection).filter(
        Selection.student_id == student_id,
        Selection.period_id == period.id,
        Selection.course_id == course_id,
    ).with_for_update().first()
    if not existing and len(active_selections) >= MAX_COURSES_PER_STUDENT:
        raise HTTPException(
            status_code=400,
            detail="student can select at most two courses",
        )
    if existing and existing.status == "FINAL":
        raise HTTPException(status_code=400, detail="student already finalized")

    selected_count = db.query(Selection).filter(
        Selection.course_id == course_id,
        Selection.status.in_(["SELECTED", "FINAL"]),
    ).count()
    increases_count = existing is None or existing.status == "WAITING"

    if increases_count and selected_count >= course.capacity and not allow_over_capacity:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "COURSE_CAPACITY_EXCEEDED",
                "message": "course capacity will be exceeded",
                "capacity": course.capacity,
                "selected_count": selected_count,
            },
        )

    if existing:
        existing.status = "FINAL"
        existing.period_id = course.period_id
        existing.queue_position = None
    elif period_record:
        period_record.course_id = course_id
        period_record.status = "FINAL"
        period_record.selected_time = app_now()
        period_record.queue_position = None
    else:
        db.add(Selection(
            course_id=course_id,
            period_id=course.period_id,
            student_id=student_id,
            selected_time=app_now(),
            status="FINAL",
        ))

    db.flush()
    if period.status != "CLOSED":
        update_selection_status(course_id, db, commit=False)
    db.commit()

    new_count = db.query(Selection).filter(
        Selection.course_id == course_id,
        Selection.status.in_(["SELECTED", "FINAL"]),
    ).count()
    return {
        "message": "student added",
        "selected_count": new_count,
        "capacity": course.capacity,
        "over_capacity": new_count > course.capacity,
    }


@router.delete("/course/{course_id}/remove_student")
def admin_remove_student(
    course_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_required),
):
    sync_period_statuses(db)
    course_snapshot = db.query(Course).filter(Course.id == course_id).first()
    if not course_snapshot:
        raise HTTPException(status_code=404, detail="course not found")
    if course_snapshot.period_id is None:
        raise HTTPException(status_code=400, detail="course is not assigned to a period")

    period = lock_period_for_write(db, course_snapshot.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="period not found")
    student = db.query(Student).filter(
        Student.id == student_id
    ).with_for_update().first()
    if not student:
        raise HTTPException(status_code=404, detail="student not found")
    course = db.query(Course).filter(
        Course.id == course_id
    ).with_for_update().first()
    if not course or course.period_id != period.id:
        raise HTTPException(status_code=409, detail="course period changed; please retry")

    selection = db.query(Selection).filter(
        Selection.course_id == course_id,
        Selection.student_id == student_id,
    ).with_for_update().first()
    if not selection:
        raise HTTPException(status_code=404, detail="student not found")

    db.delete(selection)
    db.flush()
    if period.status != "CLOSED":
        update_selection_status(course_id, db, commit=False)
    db.commit()

    return {"message": "student removed"}
