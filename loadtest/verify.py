"""Read-only consistency checks after selection.js against the test database."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import engine


if not (engine.url.database or "").endswith("_loadtest"):
    raise SystemExit("Only a database ending in _loadtest is allowed")
queries = {
    "students_not_at_two": """SELECT count(*) FROM (
        SELECT st.id FROM students st LEFT JOIN selections s ON s.student_id=st.id
            AND s.status IN ('SELECTED','WAITING','FINAL')
        GROUP BY st.id HAVING count(s.id) <> 2) x""",
    "over_capacity": """SELECT count(*) FROM (
        SELECT c.id FROM courses c JOIN selections s ON s.course_id=c.id
        WHERE s.status IN ('SELECTED','FINAL') GROUP BY c.id, c.capacity
        HAVING count(*) > c.capacity) x""",
    "ranking_mismatch": """WITH ranked AS (
        SELECT s.status,
            greatest(c.capacity - (
                SELECT count(*) FROM selections f
                WHERE f.course_id = c.id AND f.status = 'FINAL'
            ), 0) AS slots,
            row_number() OVER (PARTITION BY s.course_id ORDER BY s.selected_time, s.id) AS position
        FROM selections s JOIN courses c ON c.id=s.course_id
        WHERE s.status IN ('SELECTED','WAITING'))
        SELECT count(*) FROM ranked
        WHERE status IS DISTINCT FROM CASE
            WHEN position <= slots THEN 'SELECTED' ELSE 'WAITING' END""",
}
with engine.connect() as connection:
    violations = {name: connection.execute(text(sql)).scalar() for name, sql in queries.items()}
print(violations)
raise SystemExit(any(violations.values()))
