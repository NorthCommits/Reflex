-- Creates the read-only role at database initialisation time.
-- SELECT grants on the actual tables are applied later by entrypoint.sh,
-- after Alembic has created them.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'reflex_reader') THEN
    CREATE ROLE reflex_reader WITH LOGIN PASSWORD 'reflex_reader';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE reflex TO reflex_reader;
GRANT USAGE ON SCHEMA public TO reflex_reader;

-- Covers tables created after this point by the migrating role, so future
-- tables are readable by reflex_reader without another manual grant.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO reflex_reader;
