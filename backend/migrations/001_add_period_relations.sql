BEGIN;

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS period_id INTEGER;

ALTER TABLE selections
    ADD COLUMN IF NOT EXISTS period_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_courses_period_id'
    ) THEN
        ALTER TABLE courses
            ADD CONSTRAINT fk_courses_period_id
            FOREIGN KEY (period_id) REFERENCES periods(id) ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_selections_period_id'
    ) THEN
        ALTER TABLE selections
            ADD CONSTRAINT fk_selections_period_id
            FOREIGN KEY (period_id) REFERENCES periods(id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_courses_period_id ON courses(period_id);
CREATE INDEX IF NOT EXISTS ix_selections_period_id ON selections(period_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_periods_single_open
    ON periods ((1))
    WHERE status IN ('WAITING', 'ACTIVE');

COMMIT;
