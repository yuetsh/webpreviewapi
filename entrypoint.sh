#!/bin/sh

python manage.py migrate --noinput
exec gunicorn --bind 0.0.0.0:8000 api.asgi:application -k uvicorn.workers.UvicornWorker --workers 5