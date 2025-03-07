#!/bin/sh

python manage.py migrate --noinput
exec gunicorn api.wsgi --bind :8000 -k uvicorn.workers.UvicornWorker --workers 5 --threads 4