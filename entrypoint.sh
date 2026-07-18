#!/bin/sh
set -e

# pg_isready and psql expect a libpq connection string, not the
# SQLAlchemy "+psycopg" driver suffix.
PLAIN_DATABASE_URL=$(echo "$DATABASE_URL" | sed 's/+psycopg//')

echo "waiting for database..."
until pg_isready -d "$PLAIN_DATABASE_URL" >/dev/null 2>&1; do
  sleep 1
done
echo "database is reachable"

echo "running migrations..."
alembic upgrade head

echo "applying read-only grants..."
psql "$PLAIN_DATABASE_URL" -v ON_ERROR_STOP=1 -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO reflex_reader;"

echo "seeding database..."
python seed.py

echo "starting server..."
exec uvicorn reflex.api:app --host 0.0.0.0 --port 8000
