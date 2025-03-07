#!/bin/sh

python manage.py migrate --noinput
exec gunicorn api.wsgi -k uvicorn.workers.UvicornWorker -w 5