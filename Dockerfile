# 多阶段构建：前端 + 后端

# ------------------------------------------------------------------------------
# Stage 1: 构建前端
# ------------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web

# 复制前端依赖文件
COPY web/package.json web/package-lock.json ./
RUN npm ci

# 复制前端源码并构建
COPY web/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Python 后端
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS backend

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e .

# 复制后端源码
COPY src/ ./src/
COPY config/ ./config/
COPY templates/ ./templates/
COPY web_app.py ./

# 复制前端构建产物
COPY --from=frontend-builder /app/web/dist ./web/dist

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV FRONTEND_DIST=/app/web/dist
ENV FLASK_PORT=5000
ENV FLASK_DEBUG=false
ENV LOG_LEVEL=INFO

EXPOSE 5000

CMD ["python", "web_app.py"]
