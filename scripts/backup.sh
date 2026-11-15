#!/bin/sh
# Back up the database (pg_dump, custom format) and uploaded files into backups/.
# Usage: scripts/backup.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p backups && chmod 700 backups
stamp=$(date +%Y%m%d_%H%M%S)
umask 077

docker compose exec -T db pg_dump -U lms -d lms -Fc > "backups/db_$stamp.dump"
docker compose exec -T web tar -C /data -czf - uploads 2>/dev/null > "backups/uploads_$stamp.tar.gz" || true

echo "Đã sao lưu:"
ls -lh "backups/db_$stamp.dump" "backups/uploads_$stamp.tar.gz" 2>/dev/null
