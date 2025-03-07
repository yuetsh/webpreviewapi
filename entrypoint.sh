#!/bin/sh

python manage.py migrate --noinput
exec gunicorn api.wsgi -k uvicorn.workers.UvicornWorker --workers 5 --threads 4