#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# PLDiagnosis 一键重启脚本
# 用法: ./start.sh
# 行为: 杀掉本项目全部旧进程(Flask 5000 + MCP 服务 8001-8005)，
#       后台重启所有服务并构建前端，最后逐个健康检查。
# ------------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

echo "==> 1/4 停止旧进程..."
for port in 5000 8001 8002 8003 8004 8005; do
    pids=$(lsof -ti :$port -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
        kill -9 $pids 2>/dev/null || true
        echo "    端口 $port 已停止 (pid: $pids)"
    fi
done
sleep 1

echo "==> 2/4 启动 MCP 服务..."
start_service() {
    # $1=服务目录 $2=端口
    (cd "mcp-services/$1" && nohup python3 main.py > server_start.log 2>&1 &)
    echo "    $1 (端口 $2) 已启动"
}
start_service lightning-service 8001
start_service icing-service 8002
start_service wind-service 8003
start_service bird-service 8004
start_service weather-service 8005

echo "==> 3/4 构建前端..."
(cd web && npm run build > /dev/null 2>&1)
echo "    前端构建完成 (web/dist)"

echo "==> 4/4 启动 Flask 后端..."
nohup python3 web_app.py > server.log 2>&1 &
echo $! > server.pid
sleep 4

echo ""
echo "==> 健康检查..."
check() {
    # $1=名称 $2=url
    if curl -s -m 5 "$2" | grep -q '"ok"'; then
        echo "    [OK]   $1 ($2)"
    else
        echo "    [FAIL] $1 ($2)"
    fi
}
check "Flask 后端      " "http://localhost:5000/api/health"
check "雷电诊断 (8001) " "http://localhost:8001/health"
check "覆冰监测 (8002) " "http://localhost:8002/health"
check "风偏诊断 (8003) " "http://localhost:8003/health"
check "鸟害监测 (8004) " "http://localhost:8004/health"
check "微气象诊断 (8005)" "http://localhost:8005/health"

echo ""
echo "完成。访问 http://localhost:5000"
echo "日志: server.log (Flask) / mcp-services/*/server_start.log (MCP 服务)"
