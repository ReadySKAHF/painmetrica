#!/bin/sh
set -e

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn..."
exec gunicorn Painmetrica.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class gthread \
    --threads 4 \
    --timeout 30 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --limit-request-line 4094 \
    --limit-request-fields 100 \
    --access-logfile logs/gunicorn_access.log \
    --error-logfile logs/gunicorn_error.log \
    --log-level warning
