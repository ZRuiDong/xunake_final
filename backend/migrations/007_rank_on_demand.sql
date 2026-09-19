-- Numeric queue positions are derived from the canonical ordering when read.
-- Keeping them in sync made every hot-course application rewrite many rows.
UPDATE selections SET queue_position = NULL
WHERE queue_position IS NOT NULL;

-- Supports first-come-first-served waitlist promotion and ordered detail views.
CREATE INDEX IF NOT EXISTS ix_selections_course_status_time_id
    ON selections (course_id, status, selected_time, id);
