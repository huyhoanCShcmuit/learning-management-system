#!/bin/sh
# Copy the cloud database into the local db container (for development/testing).
# Reads the cloud URL from secrets/cloud_database_url (never typed on the command line).
#   echo 'postgres://user:pass@host:5432/dbname?sslmode=require' > secrets/cloud_database_url
# Usage: scripts/pull_cloud_db.sh
set -e
cd "$(dirname "$0")/.."
src=secrets/cloud_database_url
[ -s "$src" ] || { echo "Chưa có $src"; exit 1; }
mkdir -p backups && chmod 700 backups
umask 077
stamp=$(date +%Y%m%d_%H%M%S)
out="backups/cloud_$stamp.dump"

# Pass the URL through an env file so it does not show up in the process list.
envfile=$(mktemp)
trap 'rm -f "$envfile"' EXIT
printf 'PGURL=%s\n' "$(cat "$src")" > "$envfile"
docker run --rm --env-file "$envfile" postgres:18-alpine sh -c 'pg_dump "$PGURL" -Fc --no-owner' > "$out"
echo "Đã tải bản sao cloud: $out"

scripts/restore.sh "$out"
