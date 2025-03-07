#!/bin/sh

python manage.py migrate --noinput
exec gunicorn -w 5  -k uvicorn.workers.UvicornWorker api.asgi:application