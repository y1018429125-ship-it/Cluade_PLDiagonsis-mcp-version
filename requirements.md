# PLDiagnosis 项目需求分析

> 本文档面向新加入的开发者或新的 Claude 对话实例，帮助快速理解 PLDiagnosis 项目的总体目标、核心能力、技术架构和当前状态。
>
> 版本：0.2.0-alpha | 最后更新：2026-07-17

---

## 第一部分：概念指南（User-Facing Conceptual Layer）

### 1. 项目概述

**PLDiagnosis** 是一个基于大语言模型（LLM）的输电线路故障综合诊断智能体系统。用户通过自然语言描述线路故障情况，系统自动解析故障上下文，调用多种专业诊断工具（雷电、覆冰、风偏、鸟害、天气等），综合分析后生成标准化、可解释的诊断报告。

**核心使用场景**：

运维人员或分析人员面对一条特高压输电线路跳闸记录时，需要快速判断故障类型和原因。传统方式需要逐个登录系统、查看多个模块数据并人工综合分析。PLDiagnosis 将这一过程自动化：

1. **用户输入故障描述** → 系统自动解析线路名、故障时间、电压等级等关键信息
2. **LLM 规划诊断方案** → 决定调用哪些诊断工具
3. **并行/串行执行工具** → 各工具独立返回诊断证据和置信度
4. **LLM 生成综合报告** → 加权分析各工具输出，给出最终故障类型、置信度和处理建议
5. **人在回路交互** → 用户可排除工具、调整权重、复查结果、修改报告并保存为技能

**关键特性**：

- **自然语言交互**：用户无需学习专业命令，直接描述故障情况
- **多工具协同诊断**：雷电、覆冰、风偏、鸟害、天气等多类工具可并行执行
- **工具权重机制**：每个工具有默认权重，支持用户动态调整
- **人在回路（Human-in-the-Loop）**：支持排除/恢复工具、调整权重、复查、修改报告
- **技能保存与复用**：诊断策略可保存为 Markdown 技能文件，后续直接加载
- **实时流式反馈**：通过 SSE 向前端实时推送诊断进度
- **会话持久化**：会话数据以 JSON 文件持久化，刷新页面不丢失
- **浏览器代理**：集成 Playwright 浏览器代理，可抓取网页天气数据
- **诊断全流程日志**：每次提问自动记录前端完整输出、各阶段时延、SSE 事件流和工具调用耗时，便于后续调试与性能分析

---

### 2. 系统架构

项目采用**分层架构**，受六边形/整洁架构影响：

```
┌─────────────────────────────────────────────────────────┐
│                    Interfaces 层                         │
│         (Flask 路由, SSE 流, 依赖注入容器)                 │
├─────────────────────────────────────────────────────────┤
│                  Application 层                          │
│    (命令模式: Diagnose, Exclude, Recheck, Complete...)   │
├─────────────────────────────────────────────────────────┤
│                     Domain 层                            │
│  (状态机, 会话管理, 意图分类, 工具执行, 报告生成,         │
│   诊断规划, 提示构建, 权重引擎...)                         │
├─────────────────────────────────────────────────────────┤
│                  Core 层                                 │
│         (数据模型, 配置, 异常)                             │
├─────────────────────────────────────────────────────────┤
│                Infrastructure 层                         │
│  (LLM 服务, 工具注册表, 适配器, 事件总线,                 │
│   会话仓库, 模板解析器)                                    │
└─────────────────────────────────────────────────────────┘
```

**关键架构决策**：

- **命令模式**：每个用户意图映射为一个 Command 类，统一接口 `execute(ctx) -> AsyncIterator[Event]`
- **依赖注入**：`Container` 类集中装配所有组件，避免手动传参
- **状态机**：会话状态转换受严格管控，非法转换会被拒绝
- **事件总线**：异步发布-订阅模式，解耦状态变更与事件通知
- **SSE 流式传输**：诊断进度实时推送到前端

---

### 3. 核心工作流

#### 3.1 端到端诊断流程

```
用户输入消息
    │
    ▼
POST /chat ── SSE 流开始
    │
    ├── 1. 意图分类 (IntentClassifier)
    │   └── 识别用户意图: DIAGNOSE / EXCLUDE_TOOL / RECHECK_TOOL / ...
    │
    ├── 2. 会话管理 (SessionManager)
    │   └── get_or_create(): 同一线路+日期复用未完成会话，否则新建
    │
    ├── 3. 构建执行上下文 (ExecutionContext)
    │   └── 会话 + 故障上下文 + 用户消息 + 意图
    │
    ├── 4. 解析并执行命令
    │   └── DiagnoseCommand.execute():
    │       ├── a. 状态校验 -> 转入 DIAGNOSING
    │       ├── b. 解析故障上下文 (FaultContextParser)
    │       ├── c. 加载技能 (SkillLoader)
    │       ├── d. 列出可用工具 (ToolRegistry)
    │       ├── e. 组装提示词 (PromptBuilder)
    │       ├── f. 诊断规划 (DiagnosisPlanner) ← LLM 流式输出
    │       ├── g. 执行工具 (ToolExecutor)
    │       ├── h. 生成报告 (ReportComposer) ← LLM 生成 Markdown
    │       ├── i. 计算摘要 (WeightEngine / LLM)
    │       └── j. 状态转入 MODIFYING
    │
    └── 5. SSE 流返回事件序列
        ├── event: start      → 前端显示"诊断中..."动画
        ├── event: thinking   → LLM 思考过程
        ├── event: content    → 增量内容更新
        ├── event: status     → 会话状态更新
        ├── event: complete   → 绿色摘要卡片（故障类型、置信度、操作日志）
        └── event: error      → 红色错误消息
```

#### 3.2 人在回路交互流程

诊断完成后（`MODIFYING` 状态），用户可以：

- **排除工具**：将某个工具加入排除列表，自动重新诊断
- **恢复工具**：将工具从排除列表移除，自动重新诊断
- **复查工具**：重新执行指定工具并更新结果
- **调整权重**：修改工具权重（范围 0.1-2.0），可选重新计算摘要
- **完成诊断**：将会话状态标记为 `COMPLETED`，可保存为新技能
- **继续对话**：重新进入诊断流程，修改报告

#### 3.3 权重与置信度机制

系统存在两层置信度概念：

1. **工具原始置信度**：每个 MCP tool 返回的 `structured_data.confidence`，代表该工具对自身结论的信心
2. **工具权重**：`config/config.yaml` 中配置的默认权重，或用户在会话中动态调整的权重

**加权计算方式**：

- 工具权重配置通过 PromptBuilder 写入 LLM prompt
- LLM 在生成报告时按提示进行加权计算：
  ```
  最终得分 = 工具原始置信度 × 工具权重
  ```
- LLM 比较各工具加权得分，给出最终主诊断结论
- `_extract_summary()` 仅用于前端快速摘要显示，不做最终加权判定

**默认权重**：

| 工具 | 默认权重 |
|------|----------|
| LightningDiagnosisTool | 1.0 |
| IcingDiagnosisTool | 0.9 |
| WindDiagnosisTool | 0.8 |
| BirdDamageDiagnosisTool | 0.6 |

---

### 4. 已集成的诊断工具

| 工具 | 类型 | 功能 | 端口 |
|------|------|------|------|
| LightningDiagnosisTool | MCP HTTP | 雷电故障诊断（已替换为真实数据服务） | 8001 |
| IcingDiagnosisTool | MCP HTTP | 覆冰故障诊断（模拟数据） | 8002 |
| WindDiagnosisTool | MCP HTTP | 风偏故障诊断（模拟数据，调用记录已生成） | 8003 |
| BirdDamageDiagnosisTool | MCP HTTP | 鸟害故障诊断（模拟数据，调用记录已生成） | 8004 |
| WeatherDiagnosisTool | Web Scraper | 天气数据抓取（浏览器代理） | — |

**说明**：
- 当前 MCP 调用记录仅在经过 `MCPToolAdapter` 的 HTTP 工具上生成。`WeatherDiagnosisTool` 使用浏览器代理适配器，因此不产生 `.md` 调用记录；`IcingDiagnosisTool` 在部分诊断计划中可能被智能体跳过，也可能不产生记录。
- `WeatherDiagnosisTool` 已通过提示词临时屏蔽（`DO NOT call`），原因是其浏览器代理经常超时（单次约 109 秒）。屏蔽后 `execute_tools` 阶段耗时从约 109 秒降至约 0.4 秒，前端总诊断耗时从约 2.5 分钟降至约 52 秒。
- MCP 调用记录已改为**覆盖写入**模式，仅保留每个服务的最新一次调用记录，时间戳使用北京时间（UTC+08:00）。

每个 MCP 服务都是独立的 FastAPI 微服务，暴露：
- `GET /health` — 健康检查
- `POST /diagnose` — 诊断接口

PLD 通过 `MCPToolAdapter` 使用 `httpx.AsyncClient` 调用这些 HTTP 服务。

---

### 5. 当前状态与已知限制

**当前状态**：

- 雷电诊断工具已接入真实 Mock 数据服务，并通过前端端到端验证
- 新增 MCP 调用记录功能，成功调用后会生成 `mcp-services/{service_dir}.md`（覆盖写入，北京时间）
- 新增诊断全流程日志功能，自动记录前端输出、阶段时延、SSE 事件和工具耗时
- `WeatherDiagnosisTool` 已通过提示词临时屏蔽，诊断时延显著下降
- 其余 4 个工具仍返回模拟数据
- 系统整体可运行，前端可交互

**已知限制**：

1. **LLM 配置硬编码**：`config/config.yaml` 中 base_url 和 api_key 为本地测试配置
2. **部分 MCP 服务仍使用模拟数据**：覆冰、风偏、鸟害工具未接入真实数据源
3. **output_schema 未同步**：`config/tools/lightning.yaml` 仍描述旧虚拟工具输出字段
4. **报告模板系统待完善**：`templates/` 目录为空，Word/PDF 导出未实现
5. **无前端测试**：Vue 组件缺少单元测试和 E2E 测试
6. **单用户会话存储**：当前为单用户设计，未隔离多用户数据
7. **安全加固不足**：输入校验、速率限制、认证授权待补充
8. **诊断日志待优化**：`thinking` 事件重复较多导致日志偏大，长期运行需归档策略

---

## 第二部分：技术实现细节（Agent-Facing Technical Layer）

### 1. 目录结构

```
/Users/yfzx/Desktop/Cluade_PLDiagonsis-master/
├── config/                         # 配置文件
│   ├── config.yaml                 # 主配置：LLM、权重、会话参数
│   └── tools/                      # 工具 YAML 配置
│       ├── lightning.yaml
│       ├── icing.yaml
│       ├── wind.yaml
│       ├── bird.yaml
│       └── weather.yaml
├── data/                           # 会话数据持久化
│   └── sessions.json
├── docs/                           # 设计文档
│   ├── project-summary.md
│   └── superpowers/                # 详细设计规格
├── mcp-services/                   # MCP HTTP 微服务
│   ├── lightning-service/          # 真实雷电诊断服务
│   ├── icing-service/
│   ├── wind-service/
│   ├── bird-service/
│   └── weather-service/
├── skills/                         # Markdown 技能文件
│   ├── comprehensive_diagnosis.md
│   ├── report_modifier.md
│   └── references/
├── src/                            # 主应用源码
│   ├── core/                       # 数据模型、配置、异常
│   │   ├── models.py
│   │   ├── config.py
│   │   └── exceptions.py
│   ├── domain/                     # 领域逻辑
│   │   ├── diagnosis_planner.py
│   │   ├── tool_executor.py
│   │   ├── report_composer.py
│   │   ├── report_engine.py
│   │   ├── prompt_builder.py
│   │   ├── session_manager.py
│   │   ├── state_machine.py
│   │   ├── intent_classifier.py
│   │   ├── skill_loader.py
│   │   ├── template_registry.py
│   │   └── ...
│   ├── application/                # 应用层命令
│   │   ├── commands/
│   │   │   ├── diagnose.py
│   │   │   ├── exclude_tool.py
│   │   │   ├── include_tool.py
│   │   │   ├── recheck_tool.py
│   │   │   ├── adjust_weight.py
│   │   │   ├── modify_report.py
│   │   │   ├── complete_diagnosis.py
│   │   │   ├── save_strategy.py
│   │   │   └── save_skill.py
│   │   └── context.py
│   ├── infrastructure/             # 基础设施
│   │   ├── adapters/
│   │   │   ├── mcp_adapter.py      # MCP HTTP 适配器
│   │   │   ├── base.py
│   │   │   └── registry.py
│   │   ├── llm_service.py
│   │   ├── fault_parser.py
│   │   ├── session_repository.py
│   │   ├── event_bus.py
│   │   ├── diagnosis_logger.py      # 诊断全流程日志
│   │   └── ...
│   └── interfaces/                 # 接口层
│       ├── web.py                  # Flask 路由 + SSE
│       └── dependency_injection.py
├── web/                            # Vue 3 前端
│   ├── src/
│   │   ├── App.vue
│   │   ├── components/
│   │   ├── stores/sessionStore.ts
│   │   ├── api/
│   │   └── ...
│   └── dist/                       # 构建产物
├── tests/                          # 测试
│   ├── unit/
│   └── integration/
├── web_app.py                      # Flask 入口
├── start.sh                        # 启动脚本
├── docker-compose.yml
├── requirements.txt
├── 修改.md                         # 项目修改记录
└── requirements.md                 # 本文档
```

---

### 2. 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+, Flask |
| 数据验证 | Pydantic v2, pydantic-settings |
| LLM 接口 | OpenAI-compatible API (AsyncOpenAI) |
| MCP 服务 | FastAPI + uvicorn |
| 前端 | Vue 3.5 + TypeScript + Vite |
| 状态管理 | Pinia |
| 容器化 | Docker + docker-compose |
| 测试 | pytest, pytest-asyncio, pytest-cov |
| 代码规范 | black, ruff, mypy |
| CI/CD | GitHub Actions |

---

### 3. 关键接口

#### 3.1 Web API（Flask）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/chat` | POST | 主聊天接口，返回 SSE 流 |
| `/api/sessions` | GET | 列出所有会话 |
| `/api/sessions/<id>` | GET | 获取会话详情 |
| `/api/sessions/<id>/switch` | POST | 切换当前活跃会话 |
| `/api/sessions/<id>/complete` | POST | 标记会话完成 |
| `/api/sessions/clear` | POST | 清空所有会话 |
| `/api/log/frontend` | POST | 接收前端日志并合并到诊断日志 |
| `/api/tools` | GET | 列出可用诊断工具 |
| `/api/settings` | GET | 获取默认权重、权重范围、LLM 配置 |
| `/api/settings/weights` | POST | 更新活跃会话的权重 |
| `/api/skills` | GET/POST | 列出/创建技能 |
| `/api/skills/<name>/activate` | POST | 激活技能 |
| `/api/skills/<name>` | DELETE | 删除技能 |
| `/api/health` | GET | 健康检查 |

#### 3.2 MCP 服务接口

每个 MCP 服务统一暴露：

- `GET /health`
- `POST /diagnose`

请求体：
```json
{
  "line_name": "雅湖线",
  "voltage_level": "±800",
  "fault_time": "2025-05-08T19:46:30",
  "additional_info": {
    "line_id": "...",
    "tower_id": "..."
  }
}
```

响应体：
```json
{
  "tool_name": "LightningDiagnosisTool",
  "raw_text": "Markdown 诊断报告",
  "structured_data": {
    "fault_type": "雷击-绕击",
    "confidence": 0.985,
    "evidence": [...],
    "details": {...}
  },
  "metadata": {...},
  "timestamp": "2026-07-08T..."
}
```

---

### 4. 关键代码位置

| 功能 | 文件 |
|------|------|
| LLM 调用 | `src/infrastructure/llm_service.py` |
| 意图分类 | `src/domain/intent_classifier.py` |
| 诊断规划 | `src/domain/diagnosis_planner.py` |
| 工具执行 | `src/domain/tool_executor.py` |
| MCP 适配器 | `src/infrastructure/adapters/mcp_adapter.py` |
| 报告生成 | `src/domain/report_composer.py` |
| 权重引擎 | `src/domain/report_composer.py`（LLM 驱动） |
| 会话管理 | `src/domain/session_manager.py` |
| 状态机 | `src/domain/state_machine.py` |
| 提示构建 | `src/domain/prompt_builder.py` |
| 技能加载 | `src/domain/skill_loader.py` |
| 工具注册 | `src/infrastructure/adapters/registry.py` |
| 诊断全流程日志 | `src/infrastructure/diagnosis_logger.py` |
| 前端日志发送 | `web/src/stores/sessionStore.ts` |
| 前端日志合并 | `src/interfaces/web.py` (`/api/log/frontend`) |
| 主入口 | `web_app.py` |
| 启动脚本 | `start.sh` |
| 前端状态 | `web/src/stores/sessionStore.ts` |
| 前端 API | `web/src/api/http.ts`, `web/src/api/sse.ts` |

---

### 5. 启动方式

#### 5.1 开发模式

```bash
cd /Users/yfzx/Desktop/Cluade_PLDiagonsis-master
./start.sh dev
```

该命令会：
1. 启动 5 个 MCP 服务（端口 8001-8005）
2. 安装 Python 依赖
3. 构建前端
4. 启动 Flask 服务（端口 5000）

#### 5.2 单独启动 MCP 服务

```bash
cd mcp-services/lightning-service
python3 main.py
```

#### 5.3 Docker 模式

```bash
./start.sh docker
```

---

### 6. 测试

```bash
# 运行全部测试
python3 -m pytest

# 运行单元测试
python3 -m pytest tests/unit

# 运行集成测试
python3 -m pytest tests/integration
```

---

### 7. 相关外部依赖

| 服务 | 地址 | 用途 |
|------|------|------|
| 本地 LLM 服务 | `http://172.18.179.2:20017/v1` | LLM 推理 |
| 特高压 Mock API | `http://localhost:8000` | 雷电诊断真实数据源 |

---

### 8. 文档索引

| 文档 | 用途 |
|------|------|
| `docs/project-summary.md` | 项目总结（截至 2026-05-14） |
| `docs/superpowers/plans/*.md` | 各阶段实现计划 |
| `docs/superpowers/specs/*.md` | 各模块设计规格 |
| `修改.md` | 项目修改记录 |
| `task.md` | 任务说明（本文档的配套） |

---

## 9. 后续方向

1. **前端测试**：补充 Vue 组件单元测试和 Playwright E2E 测试
2. **API 测试**：覆盖剩余 REST 端点，特别是聊天流和 SSE 事件
3. **真实数据源接入**：将覆冰、风偏、鸟害工具从模拟数据替换为真实数据
4. **报告模板系统**：完善 Word/PDF 导出
5. **多用户支持**：会话数据按用户隔离
6. **安全加固**：输入校验、速率限制、认证授权
7. **配置外部化**：将 LLM 配置、Mock API 账号密码改为环境变量
8. **诊断日志优化**：减少 `thinking` 事件冗余、增加归档策略

---

*本需求分析用于快速了解项目全貌。具体实现细节以源码为准。*
