#!/bin/sh

sleep 5

# 执行数据库迁移
python manage.py migrate --noinput

# 启动 Gunicorn
exec gunicorn api.asgi:application \
    --bind 0.0.0.0:8000 \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --threads 2