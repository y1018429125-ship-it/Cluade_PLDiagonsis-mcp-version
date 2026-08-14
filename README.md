# PLDiagnosis — 输电线路故障智能诊断系统

基于 LLM 的输电线路故障诊断 Web 系统，支持雷击、覆冰、风偏、鸟害、微气象等多类故障的综合诊断与报告生成。

## 环境要求

- Python 3.10+
- Node.js 18+（前端构建）
- **需在内网环境**：LLM 服务地址 `172.18.179.2:20017` 仅内网可达（或在 `.env` 中改为其他 OpenAI 兼容接口）
- **需先启动 Mock 接口平台**（Mock_lightning 仓库，见下方"启动顺序"）

## 部署启动

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt
pip install -r mcp-services/lightning-service/requirements.txt
pip install -r mcp-services/icing-service/requirements.txt
pip install -r mcp-services/wind-service/requirements.txt
pip install -r mcp-services/bird-service/requirements.txt
pip install -r mcp-services/weather-service/requirements.txt

# 2. 配置环境变量（按需修改 LLM 地址等）
cp .env.example .env

# 3. 安装前端依赖
cd web && npm install && cd ..

# 4. 一键启动（自动停止旧进程、启动 5 个 MCP 服务、构建前端、启动后端并健康检查）
./start.sh
```

启动成功后访问：http://localhost:5000

## 启动顺序（完整功能）

本系统依赖两个外部服务，完整测试请按以下顺序启动：

1. **Mock 接口平台**（Mock_lightning 仓库）：`python src/setup.py`，提供 `localhost:8000` 模拟接口，三个 MCP 诊断服务（雷电/风偏/微气象）都依赖它
2. **故障知识库**（fault-knowledge-base 仓库，可选）：提供 `localhost:8503` 知识库问答，不启动则仅"知识库问答"功能不可用，其余诊断功能不受影响
3. **本系统**：`./start.sh`

## 服务端口

| 端口 | 服务 |
|---|---|
| 5000 | Flask 后端 + 前端页面 |
| 8001 | 雷电诊断 MCP |
| 8002 | 覆冰监测 MCP |
| 8003 | 风偏诊断 MCP |
| 8004 | 鸟害监测 MCP |
| 8005 | 微气象诊断 MCP |

## 目录说明

| 目录/文件 | 说明 |
|---|---|
| `src/` | 后端核心代码（诊断引擎、报告生成、Web 接口） |
| `mcp-services/` | 5 个 MCP 诊断服务 |
| `web/` | Vue3 前端 |
| `config/` | 主配置 `config.yaml` 与各工具配置 |
| `start.sh` | 一键启动/重启脚本 |
| `docs/` | 项目文档 |
