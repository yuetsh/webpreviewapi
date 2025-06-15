FROM python:3.12-slim as builder

WORKDIR /app

# 配置apt使用国内镜像源
RUN echo "deb https://mirrors.ustc.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list \
    && echo "deb https://mirrors.ustc.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "deb https://mirrors.ustc.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "deb https://mirrors.ustc.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 使用国内镜像源安装依赖
RUN pip config set global.index-url https://mirrors.ustc.edu.cn/pypi/web/simple \
    && pip install --no-cache-dir -r requirements.txt

# 最终阶段
FROM python:3.12-slim

WORKDIR /app

# 创建非root用户
RUN useradd -m -u 1000 appuser

# 从builder阶段复制Python包
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# 复制应用代码
COPY . .

# 设置权限
RUN chown -R appuser:appuser /app \
    && chmod +x /app/entrypoint.sh

# 切换到非root用户
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]