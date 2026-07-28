#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Idempotent superuser creation, but only when a real password was supplied —
# a placeholder like "change-me" would otherwise become a live admin login.
if [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ] \
   && [ "${DJANGO_SUPERUSER_PASSWORD}" != "change-me" ]; then
    python manage.py createsuperuser --noinput 2>/dev/null || true
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
