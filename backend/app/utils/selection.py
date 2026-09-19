from sqlalchemy import case, func, text
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.selection import Selection
from app.models.student import Student


MAX_COURSES_PER_STUDENT = 2


def calculate_ranking(
    course_id: int,
    db: Session,
    include_rejected: bool = False,
):
    records = db.query(Selection, Student).join(
        Student,
        Selection.student_id == Student.id
    ).filter(Selection.course_id == course_id)
    if not include_rejected:
        records = records.filter(Selection.status != "REJECTED")
    return records.order_by(
        case((Selection.status == "FINAL", 0),
             (Selection.status == "REJECTED", 2), else_=1),
        Selection.selected_time, Selection.id,
    ).populate_existing().all()


def update_selection_status(course_id: int, db: Session, commit: bool = True):
    db.flush()
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Rank in one database statement; do not fetch every applicant and send
        # an UPDATE per row while holding the popular course's transaction lock.
        db.execute(text("""
            WITH ranked AS (
                SELECT s.id, row_number() OVER (
                    ORDER BY s.selected_time, s.id
                )::integer AS position,
                greatest(c.capacity - (
                    SELECT count(*) FROM selections f
                    WHERE f.course_id = c.id AND f.status = 'FINAL'
                ), 0) AS slots
                FROM selections s JOIN courses c ON c.id = s.course_id
                WHERE s.course_id = :course_id
                  AND s.status IN ('SELECTED', 'WAITING')
            ), desired AS (
                SELECT id, position,
                    CASE WHEN position <= slots THEN 'SELECTED'
                         ELSE 'WAITING' END AS status
                FROM ranked
            )
            UPDATE selections s SET status = d.status, queue_position = NULL
            FROM desired d WHERE s.id = d.id
              AND (s.status IS DISTINCT FROM d.status
                   OR s.queue_position IS NOT NULL)
        """), {"course_id": course_id})
        db.execute(text("""UPDATE selections SET queue_position = NULL
            WHERE course_id = :course_id AND status = 'FINAL'
              AND queue_position IS NOT NULL"""), {"course_id": course_id})
        for instance in list(db.identity_map.values()):
            if isinstance(instance, Selection):
                db.expire(instance, ["status", "queue_position"])
        if commit:
            db.commit()
        return

    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        return

    ranking = calculate_ranking(course_id, db)
    final_count = sum(
        1 for item in ranking if item.Selection.status == "FINAL"
    )
    available_slots = max(course.capacity - final_count, 0)
    queue_position = 0

    for item in ranking:
        selection = item.Selection

        if selection.status == "FINAL":
            selection.queue_position = None
            continue

        queue_position += 1
        # Ranking is calculated on demand. Persisting every queue position
        # turns one application into hundreds of row writes on a hot course.
        selection.queue_position = None
        selection.status = (
            "SELECTED" if queue_position <= available_slots else "WAITING"
        )

    if commit:
        db.commit()


def insert_selection_into_ranking(
    course: Course,
    selection: Selection,
    db: Session,
):
    """Admit immediately when capacity remains; otherwise join the waitlist.

    The caller must hold a FOR UPDATE lock on the course row. This makes the
    first-come-first-served decision atomic for concurrent requests.
    """
    db.flush()
    admitted_count = db.query(func.count(Selection.id)).filter(
        Selection.course_id == course.id,
        Selection.status.in_(["SELECTED", "FINAL"]),
        Selection.id != selection.id,
    ).scalar()

    selection.queue_position = None
    selection.status = (
        "SELECTED" if admitted_count < course.capacity else "WAITING"
    )


def remove_selection_from_ranking(
    course: Course,
    removed_status: str,
    db: Session,
):
    """Promote the best waiting student when an admitted student withdraws.

    The caller must hold the course lock and must flush the deletion first.
    """
    if removed_status != "SELECTED":
        return
    final_count = db.query(func.count(Selection.id)).filter(
        Selection.course_id == course.id,
        Selection.status == "FINAL",
    ).scalar()
    slots = max(course.capacity - final_count, 0)
    selected_count = db.query(func.count(Selection.id)).filter(
        Selection.course_id == course.id,
        Selection.status == "SELECTED",
    ).scalar()
    if selected_count >= slots:
        return

    promoted = db.query(Selection).filter(
        Selection.course_id == course.id,
        Selection.status == "WAITING",
    ).order_by(
        Selection.selected_time,
        Selection.id,
    ).first()
    if promoted:
        promoted.status = "SELECTED"
        promoted.queue_position = None
