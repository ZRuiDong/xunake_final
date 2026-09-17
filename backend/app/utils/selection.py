from sqlalchemy import case, text
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
        Student.weight.desc(), Selection.selected_time, Selection.id,
    ).populate_existing().all()


def update_selection_status(course_id: int, db: Session, commit: bool = True):
    db.flush()
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Rank in one database statement; do not fetch every applicant and send
        # an UPDATE per row while holding the popular course's transaction lock.
        db.execute(text("""
            WITH ranked AS (
                SELECT s.id, row_number() OVER (
                    ORDER BY st.weight DESC, s.selected_time, s.id
                )::integer AS position,
                greatest(c.capacity - (
                    SELECT count(*) FROM selections f
                    WHERE f.course_id = c.id AND f.status = 'FINAL'
                ), 0) AS slots
                FROM selections s JOIN students st ON st.id = s.student_id
                JOIN courses c ON c.id = s.course_id
                WHERE s.course_id = :course_id
                  AND s.status IN ('SELECTED', 'WAITING')
            ), desired AS (
                SELECT id, position,
                    CASE WHEN position <= slots THEN 'SELECTED'
                         ELSE 'WAITING' END AS status
                FROM ranked
            )
            UPDATE selections s SET status = d.status, queue_position = d.position
            FROM desired d WHERE s.id = d.id
              AND (s.status IS DISTINCT FROM d.status
                   OR s.queue_position IS DISTINCT FROM d.position)
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
        selection.queue_position = queue_position
        selection.status = (
            "SELECTED" if queue_position <= available_slots else "WAITING"
        )

    if commit:
        db.commit()
