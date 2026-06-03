FROM python:3.12.2-alpine AS builder

WORKDIR /app

# 配置apk使用清华镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories

# 安装构建依赖
RUN apk add --no-cache build-base

# 复制依赖文件
COPY requirements.txt .

# 使用清华镜像源安装依赖
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install --no-cache-dir -r requirements.txt

# 最终阶段
FROM python:3.12.2-alpine

WORKDIR /app

# 从builder阶段复制Python包
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# 复制应用代码
COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]