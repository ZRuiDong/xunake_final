BEGIN;

ALTER TABLE selections
    DROP CONSTRAINT IF EXISTS ck_selections_status;

UPDATE selections AS selection
SET status = 'REJECTED', queue_position = NULL
FROM periods AS period
WHERE selection.period_id = period.id
  AND period.status = 'CLOSED'
  AND selection.status = 'WAITING';

ALTER TABLE selections
    ADD CONSTRAINT ck_selections_status
    CHECK (status IN ('WAITING', 'SELECTED', 'FINAL', 'REJECTED'));

DROP INDEX IF EXISTS one_course_per_student;

CREATE UNIQUE INDEX one_course_per_student
    ON selections(student_id)
    WHERE status IN ('WAITING', 'SELECTED', 'FINAL');

CREATE UNIQUE INDEX IF NOT EXISTS one_selection_per_student_period
    ON selections(student_id, period_id);

COMMIT;
