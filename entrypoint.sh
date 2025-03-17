#!/bin/sh

# 等待 Redis 和 PgBouncer 准备就绪
sleep 5

# 执行数据库迁移
python manage.py migrate --noinput

# 启动 Gunicorn
exec gunicorn api.asgi:application \
    --bind 0.0.0.0:8000 \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --threads 2 \
    --timeout 120 \
    --keep-alive 65 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --log-level info