#!/bin/sh

python manage.py migrate --noinput
exec gunicorn --bind :8000 --workers 5 api.asgi:application -k uvicorn.workers.UvicornWorker