#!/bin/sh

# 等待数据库就绪
echo "Waiting for database..."
sleep 5

# 执行数据库迁移
echo "Running database migrations..."
python manage.py migrate --noinput

# 收集静态文件
echo "Collecting static files..."
python manage.py collectstatic --noinput

# 计算worker数量 (CPU核心数 * 2 + 1)
WORKERS=$(python -c 'import multiprocessing; print(multiprocessing.cpu_count() * 2 + 1)')

# 确保媒体目录存在并有正确的权限
echo "Setting up media directory..."
mkdir -p /app/media
chown -R appuser:appuser /app/media
chmod 755 /app/media

# 启动 Gunicorn
echo "Starting Gunicorn with $WORKERS workers..."
exec gunicorn api.asgi:application \
    --bind 0.0.0.0:8000 \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers $WORKERS \
    --threads 2 \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --keep-alive 5 \
    --log-level error \
    --capture-output \
    --enable-stdio-inheritance