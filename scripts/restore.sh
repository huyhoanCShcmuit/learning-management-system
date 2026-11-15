#!/bin/sh
# Restore a database dump made by backup.sh (or pull_cloud_db.sh) into the db container.
# Usage: scripts/restore.sh backups/db_YYYYmmdd_HHMMSS.dump
# WARNING: replaces the current contents of the local database.
set -e
cd "$(dirname "$0")/.."
dump="$1"
[ -f "$dump" ] || { echo "Không thấy file: $dump"; exit 1; }

printf "Ghi đè database hiện tại bằng %s? Gõ 'yes' để tiếp tục: " "$dump"
read -r answer
[ "$answer" = "yes" ] || { echo "Đã huỷ."; exit 1; }

docker compose stop web
docker compose exec -T db pg_restore -U lms -d lms --clean --if-exists --no-owner < "$dump"
docker compose start web
echo "Đã khôi phục."
