BEGIN;

DROP INDEX IF EXISTS one_course_per_student;
DROP INDEX IF EXISTS one_selection_per_student_period;

CREATE UNIQUE INDEX IF NOT EXISTS one_active_selection_per_student_course
    ON selections(student_id, course_id)
    WHERE status IN ('WAITING', 'SELECTED', 'FINAL');

CREATE UNIQUE INDEX IF NOT EXISTS one_selection_per_student_period_course
    ON selections(student_id, period_id, course_id);

CREATE OR REPLACE FUNCTION enforce_student_selection_limit()
RETURNS TRIGGER AS $$
DECLARE
    active_selection_count INTEGER;
BEGIN
    IF NEW.status NOT IN ('WAITING', 'SELECTED', 'FINAL') THEN
        RETURN NEW;
    END IF;

    PERFORM 1
    FROM students
    WHERE id = NEW.student_id
    FOR UPDATE;

    SELECT COUNT(*)
    INTO active_selection_count
    FROM selections
    WHERE student_id = NEW.student_id
      AND status IN ('WAITING', 'SELECTED', 'FINAL')
      AND id IS DISTINCT FROM NEW.id;

    IF active_selection_count >= 2 THEN
        RAISE EXCEPTION 'student cannot select more than two courses'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_student_selection_limit ON selections;

CREATE TRIGGER trg_student_selection_limit
BEFORE INSERT OR UPDATE OF student_id, status
ON selections
FOR EACH ROW
EXECUTE FUNCTION enforce_student_selection_limit();

COMMIT;
