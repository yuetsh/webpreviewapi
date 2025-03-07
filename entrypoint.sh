#!/bin/sh

python manage.py migrate --noinput
exec gunicorn --bind :8000 --workers 3 api.asgi:application