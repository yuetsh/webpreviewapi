#!/bin/sh

python manage.py migrate --noinput
exec gunicorn --bind 0.0.0.0:8000 api.wsgi:application -w 5