#!/bin/sh
# In demo mode Grocy uses per-locale databases (grocy_en.db, grocy_de.db, …).
# Seed the API key into every locale database that exists.
set -e

API_KEY="test_local_devenv"

SQL="INSERT INTO api_keys (api_key, user_id, expires, key_type, description)
VALUES ('${API_KEY}', 1, '2999-12-31 23:59:59', 'default', 'dev env key')
ON CONFLICT(api_key) DO UPDATE SET
  user_id=excluded.user_id,
  expires=excluded.expires,
  key_type=excluded.key_type,
  description=excluded.description;"

seeded=0
for db in /config/data/grocy_*.db; do
  [ -f "$db" ] || continue
  echo "Seeding API key into $db ..."
  sqlite3 "$db" "$SQL"
  seeded=$((seeded + 1))
done

if [ "$seeded" -eq 0 ]; then
  echo "ERROR: no grocy_*.db databases found — is the container healthy?" >&2
  exit 1
fi

echo "Done — seeded $seeded database(s)."
