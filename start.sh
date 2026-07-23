#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ------------------------------------------------------------------------------
# PLDiagnosis 启动脚本
# ------------------------------------------------------------------------------

MODE="${1:-dev}"

if [ "$MODE" = "dev" ]; then
    echo "启动开发环境..."

    # 启动 MCP 服务
    echo "启动 MCP 服务..."
    trap 'echo "停止 MCP 服务..."; kill $LIGHTNING_PID $ICING_PID $WIND_PID $BIRD_PID $WEATHER_PID 2>/dev/null || true' EXIT
    python3 mcp-services/lightning-service/main.py &
    LIGHTNING_PID=$!
    python3 mcp-services/icing-service/main.py &
    ICING_PID=$!
    python3 mcp-services/wind-service/main.py &
    WIND_PID=$!
    python3 mcp-services/bird-service/main.py &
    BIRD_PID=$!
    python3 mcp-services/weather-service/main.py &
    WEATHER_PID=$!

    sleep 2
    echo "MCP 服务已启动"

    # 检查 Python 依赖
    if ! python3 -c "import flask" 2>/dev/null; then
        echo "安装 Python 依赖..."
        pip3 install -e .
    fi

    # 构建前端
    if [ -d "web" ]; then
        echo "构建前端..."
        cd web
        if [ ! -d "node_modules" ]; then
            npm install
        fi
        npm run build
        cd ..
    fi

    # 启动后端
    echo "启动 Flask 服务 http://localhost:5000"
    export FLASK_DEBUG=true
    export FRONTEND_DIST=web/dist
    python3 web_app.py

elif [ "$MODE" = "docker" ]; then
    echo "启动 Docker 环境..."
    docker-compose up --build

else
    echo "用法: ./start.sh [dev|docker]"
    echo "  dev    - 启动开发服务器（默认）"
    echo "  docker - 使用 Docker 部署"
    exit 1
fi
