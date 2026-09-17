BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_periods_single_open
    ON periods ((1)) WHERE status IN ('WAITING', 'ACTIVE');
CREATE INDEX IF NOT EXISTS ix_courses_period_id ON courses(period_id);
CREATE INDEX IF NOT EXISTS ix_selections_course_status ON selections(course_id, status);

CREATE OR REPLACE FUNCTION enforce_student_selection_limit()
RETURNS TRIGGER AS $$
DECLARE
    active_selection_count INTEGER;
BEGIN
    IF NEW.status NOT IN ('WAITING', 'SELECTED', 'FINAL') THEN
        RETURN NEW;
    END IF;
    -- Reranking never increases occupancy. Locking other students here causes
    -- a cycle with requests holding a student lock while waiting for this course.
    IF TG_OP = 'UPDATE' THEN
        IF OLD.student_id = NEW.student_id
           AND OLD.status IN ('WAITING', 'SELECTED', 'FINAL') THEN
            RETURN NEW;
        END IF;
    END IF;
    PERFORM 1 FROM students WHERE id = NEW.student_id FOR UPDATE;
    SELECT COUNT(*) INTO active_selection_count FROM selections
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
BEFORE INSERT OR UPDATE OF student_id, status ON selections
FOR EACH ROW EXECUTE FUNCTION enforce_student_selection_limit();

COMMIT;
