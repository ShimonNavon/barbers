#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Idempotent superuser creation from DJANGO_SUPERUSER_* env vars
python manage.py createsuperuser --noinput 2>/dev/null || true

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
