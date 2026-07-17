#!/bin/bash
# Run this once to create the PostgreSQL user and database
# Usage: sudo -u postgres bash setup_db.sh

set -e

psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dukani') THEN
    CREATE USER dukani WITH PASSWORD 'dukani_secret';
    RAISE NOTICE 'User dukani created.';
  ELSE
    ALTER USER dukani WITH PASSWORD 'dukani_secret';
    RAISE NOTICE 'User dukani password updated.';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE dukani_pos OWNER dukani'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'dukani_pos')
\gexec

GRANT ALL PRIVILEGES ON DATABASE dukani_pos TO dukani;
SQL

echo "Done. Database 'dukani_pos' and user 'dukani' are ready."
