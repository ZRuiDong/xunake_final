# Database migrations

Run these commands from `backend`, with its `.env` configured.

New empty database:

```shell
python init_db.py
```

Existing untracked database **already migrated through 004**:

```shell
python migrate.py --baseline 004
```

An earlier installation must specify the last migration actually applied,
e.g. `--baseline 001`. Back up first. Baseline does not execute skipped scripts:
never use it to pretend an old database is current.

All subsequent updates:

```shell
python migrate.py
```

`schema_migrations` tracks completed versions; changes and version records are
committed atomically, with an advisory lock against concurrent migration runs.
`init_db.py` installs current models AND PostgreSQL guards for a fresh database.

Do not rerun historical SQL manually: migration 002 enforces the old one-course
rule and is not safe to replay after enabling two courses. SQLAlchemy URLs such
as `postgresql+psycopg2://...` also cannot be passed directly to `psql`; use a
PostgreSQL URI or explicit host/user/database flags instead.

001: period relations and single-open-period guard.
002: legacy one-course integrity constraints and password/session fields.
003: rejected applications no longer consume future eligibility.
004: two active applications/final enrollments per student.
005: avoid student locks during reranking; indexes and fresh-install guards.
006: deletion audit snapshots, without passwords or cascading foreign keys.
