#!/bin/sh
set -e

# The secret key lives only in the data volume (never in .env or the image).
if [ -z "$DJANGO_SECRET_KEY" ]; then
  if [ ! -f /data/secret_key ]; then
    (umask 077; python -c "import secrets; print(secrets.token_urlsafe(50))" > /data/secret_key)
  fi
  DJANGO_SECRET_KEY=$(cat /data/secret_key)
  export DJANGO_SECRET_KEY
fi

python manage.py migrate --noinput

if [ "$SEED_DEMO" = "1" ]; then
  python manage.py seed_demo
fi

# No admin password is ever passed in here: the first admin is created
# interactively with `manage.py createsuperuser` (see setup.sh).
exec "$@"
