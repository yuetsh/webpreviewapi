#!/bin/sh

python manage.py migrate --noinput
exec gunicorn --bind :8000 api.wsgi -k uvicorn.workers.UvicornWorker --workers 5 --threads 4