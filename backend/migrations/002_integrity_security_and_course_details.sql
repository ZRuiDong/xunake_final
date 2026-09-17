BEGIN;

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS instructor VARCHAR(100),
    ADD COLUMN IF NOT EXISTS location VARCHAR(200),
    ADD COLUMN IF NOT EXISTS schedule VARCHAR(200);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM selections WHERE period_id IS NULL) THEN
        RAISE EXCEPTION 'cannot enforce selections.period_id NOT NULL: null values exist';
    END IF;
    IF EXISTS (
        SELECT 1 FROM selections GROUP BY student_id HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'cannot enforce one course per student: duplicate selections exist';
    END IF;
    IF EXISTS (
        SELECT 1 FROM courses GROUP BY name HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'cannot enforce unique course names: duplicate names exist';
    END IF;
    IF EXISTS (
        SELECT 1 FROM students GROUP BY user_id HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'cannot enforce one student profile per user: duplicates exist';
    END IF;
END $$;

ALTER TABLE selections
    ALTER COLUMN student_id SET NOT NULL,
    ALTER COLUMN course_id SET NOT NULL,
    ALTER COLUMN period_id SET NOT NULL,
    ALTER COLUMN selected_time SET NOT NULL,
    ALTER COLUMN status SET NOT NULL;

ALTER TABLE periods
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN start_time SET NOT NULL,
    ALTER COLUMN end_time SET NOT NULL,
    ALTER COLUMN status SET NOT NULL;

ALTER TABLE courses
    ALTER COLUMN status SET NOT NULL;

ALTER TABLE students
    ALTER COLUMN weight SET NOT NULL,
    ALTER COLUMN created_time SET NOT NULL;

ALTER TABLE users
    ALTER COLUMN role SET NOT NULL,
    ALTER COLUMN created_time SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS one_course_per_student
    ON selections(student_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_courses_name
    ON courses(name);

CREATE UNIQUE INDEX IF NOT EXISTS uq_students_user_id
    ON students(user_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_selections_status'
    ) THEN
        ALTER TABLE selections ADD CONSTRAINT ck_selections_status
            CHECK (status IN ('WAITING', 'SELECTED', 'FINAL'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_periods_status'
    ) THEN
        ALTER TABLE periods ADD CONSTRAINT ck_periods_status
            CHECK (status IN ('WAITING', 'ACTIVE', 'CLOSED'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_periods_time_range'
    ) THEN
        ALTER TABLE periods ADD CONSTRAINT ck_periods_time_range
            CHECK (end_time > start_time);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_courses_capacity_positive'
    ) THEN
        ALTER TABLE courses ADD CONSTRAINT ck_courses_capacity_positive
            CHECK (capacity > 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_courses_status'
    ) THEN
        ALTER TABLE courses ADD CONSTRAINT ck_courses_status
            CHECK (status IN ('OPEN', 'CLOSED'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_role'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_role
            CHECK (role IN ('ADMIN', 'STUDENT'));
    END IF;
END $$;

COMMIT;
