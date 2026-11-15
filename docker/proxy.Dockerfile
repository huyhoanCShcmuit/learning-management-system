# Frontend edge: Caddy + all static assets (CSS, JS, icons, admin assets).
# Rebuilt and redeployed on its own when files under courses/static/ change.
FROM python:3.15-slim AS static
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput

FROM caddy:2.10-alpine
COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=static /app/staticfiles /srv/static
