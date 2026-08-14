# PLDiagnosis 项目需求分析

> 本文档面向新加入的开发者或新的 Claude 对话实例，帮助快速理解 PLDiagnosis 项目的总体目标、核心能力、技术架构和当前状态。
>
> 版本：0.2.0-alpha | 最后更新：2026-08-10

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
- **诊断全流程日志**：每次提问自动记录前端完整输出、各阶段时延、SSE 事件流和工具调用耗时，便于后续调试与性能分析
- **报告 LaTeX 清洗**：LLM 报告入库前经确定性清洗器处理，`$...$` 公式自动转为纯文本符号（×、≤、°等），杜绝前端渲染乱码

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
| WindDiagnosisTool | 1.0（置信度恒为 0，加权贡献 0 × 1.0 = 0，可动态调整） |
| WeatherDiagnosisTool | 1.0（置信度恒为 0，加权贡献 0 × 1.0 = 0，可动态调整） |
| BirdDamageDiagnosisTool | 已禁用（enabled: false） |

---

### 4. 已集成的诊断工具

| 工具 | 类型 | 功能 | 端口 |
|------|------|------|------|
| LightningDiagnosisTool | MCP HTTP | 雷电故障诊断（真实数据，账号 YFZX-1） | 8001 |
| IcingDiagnosisTool | MCP HTTP | 覆冰故障诊断（模拟数据，夏季/温度>5°C 时跳过） | 8002 |
| WindDiagnosisTool | MCP HTTP | 风偏参考信息（真实 getWeather 风速，仅描述不加权，账号 YFZX-3） | 8003 |
| BirdDamageDiagnosisTool | MCP HTTP | 鸟害故障诊断（已注册表级禁用，不参与诊断、前端不显示） | 8004 |
| WeatherDiagnosisTool | MCP HTTP | 气象参考信息（真实 getWeather 温湿度，仅描述不加权，账号 YFZX-2） | 8005 |

**说明**：
- 雷电、风偏、气象三个工具均消费特高压 Mock API（localhost:8000），各使用独立账号（YFZX-1/2/3）。Mock 平台单账号单 token，login 会作废同账号旧 token，多账号是并行调用无竞争的前提。
- 风偏、气象工具只输出"数据 + 一句语言描述"（风速阈值 10 m/s；湿度分档 >70%/≥40%/否则），`structured_data` 不含 confidence，对 PLD 加权诊断无贡献。风向参数 wd 弃用（298.877 与实测西南风在任何标准编码下矛盾，映射规则待确认）。
- MCP 调用记录为**覆盖写入**模式，仅保留每个服务的最新一次调用记录，时间戳使用北京时间（UTC+08:00）。`IcingDiagnosisTool` 常被规划器按季节/温度跳过，可能不产生记录；`BirdDamageDiagnosisTool` 已禁用，不再产生记录。

每个 MCP 服务都是独立的 FastAPI 微服务，暴露：
- `GET /health` — 健康检查
- `POST /diagnose` — 诊断接口

PLD 通过 `MCPToolAdapter` 使用 `httpx.AsyncClient` 调用这些 HTTP 服务。

---

### 5. 当前状态与已知限制

**当前状态**：

- 雷电诊断工具已接入真实 Mock 数据服务，并通过前端端到端验证（账号 YFZX-1）
- 气象诊断工具已重建：getWeather 温度+湿度+湿度级别描述句，仅参考不参与加权（账号 YFZX-2），已解除屏蔽
- 风偏诊断工具已重建：getWeather 风速+阈值描述句（10 m/s），仅参考不参与加权（账号 YFZX-3）；风向 wd 弃用
- 鸟害工具已在注册表级禁用（`enabled: false`），诊断与前端均不可见
- Mock 平台已支持多账号，三个工具并行调用无 token 竞争，端到端验证通过（雷击-绕击 0.985）
- MCP 调用记录为覆盖写入（北京时间），lightning/weather/wind 三份记录均正常生成
- 新增诊断全流程日志功能，自动记录前端输出、阶段时延、SSE 事件和工具耗时
- 新增报告 LaTeX 清洗器（`src/domain/report_sanitizer.py`），报告入库前自动将 `$...$` 转为纯文本，已覆盖初次诊断和修改报告两条路径，端到端验证通过
- 覆冰工具仍为模拟数据，按季节/温度条件由规划器跳过
- 新增"历史关联"功能（2026-08-11 上线，08-12 完成动态化）：诊断卡片"查看报告"旁按钮，经故障知识库 API（localhost:8503）查询两个动态问题——"{线路}历年情况"、"{province}{voltage}线路{year}年{故障月±1}月情况"（province/voltage 由 lightning 工具从 getTripInfoData 记录提取，随会话持久化）；结果按会话缓存共享并随会话持久化（08-13），点击秒开
- 报告流式输出（2026-08-14）：compose_report 改为流式（REPORT_CHUNK 事件逐字推进），工具执行完即开始生成，"查看报告"按钮在流式期间可看实时进度；历史关联预取同步提前到报告流开始，与报告生成并行（实测并发无争抢）
- 新增 `start.sh` 一键重启脚本（2026-08-12 重建）：杀旧进程 → 启动 5 个 MCP 服务 → 构建前端 → 启动 Flask → 健康检查
- 系统整体可运行，前端可交互

**已知限制**：

1. **LLM 配置硬编码**：`config/config.yaml` 中 base_url 和 api_key 为本地测试配置
2. ~~**覆冰 MCP 服务仍使用模拟数据**~~（2026-08-13 用户决策：保持现状，暂无真实数据源）：按季节/温度由规划器跳过
3. ~~**output_schema 未同步**~~（已解决 2026-08-12）：三个工具 yaml 的 output_schema 已同步真实 `structured_data` 字段
4. **报告模板系统待完善**：`templates/` 目录为空，Word/PDF 导出未实现
5. **无前端测试**：Vue 组件缺少单元测试和 E2E 测试
6. **单用户会话存储**：当前为单用户设计，未隔离多用户数据
7. **安全加固不足**：输入校验、速率限制、认证授权待补充
8. ~~**诊断日志待优化**~~（2026-08-13 已优化：thinking 累计前缀合并为单条 + result 中 images 替换占位符，单次日志约 0.4MB → 约 21KB；用户决策不做定期清理，需要时手动清理）
9. **风向参数未使用**：wd 与实测方位映射规则未确认，风偏工具仅消费风速（2026-08-13 用户决策：暂不解决，目前无法判断 wd 参数与风向的对应关系）
10. ~~**各服务账号硬编码**~~（2026-08-13 用户决策：暂缓。当前 Mock 接口的账号密码（YFZX-1/2/3）均为假凭据，明文无泄露风险；待接入真实生产接口、使用真凭据时必须外置为环境变量/.env，防止进入 git 历史）
11. ~~**知识库地址硬编码**~~（2026-08-13 已迁移：`config/config.yaml` 新增 `knowledge_base.base_url`，支持 `KB_BASE_URL` 环境变量覆盖）；~~历史关联缓存为页面存续期间有效~~（2026-08-13 已改为答案随会话持久化至 sessions.json，刷新页面/重启后端均秒开；无失效策略——知识库更新只发生在两次诊断之间，下一次诊断必为新会话、必重新查询）
12. **诊断日志时间为 UTC**：`diagnosis_logger.py` 全部使用 `datetime.now(timezone.utc)`，日志文件名与时间戳比北京时间晚 8 小时（2026-08-13 用户要求：后续改为北京时间，便于阅读）

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
| 报告 LaTeX 清洗 | `src/domain/report_sanitizer.py`（接入 `report_composer.py` 与 `modify_report.py`） |
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

> 2026-08-13 用户决策：以下长期项（前端测试、API 测试、报告模板、多用户、安全加固）目前均不考虑——当前项目为自用、单机、演示 demo，重点是对功能和性能的研究开发。保留条目备查。

1. **前端测试**：补充 Vue 组件单元测试和 Playwright E2E 测试
2. **API 测试**：覆盖剩余 REST 端点，特别是聊天流和 SSE 事件
3. **真实数据源接入**：~~覆冰工具从模拟数据替换为真实数据；鸟害工具决定恢复或正式下线~~（2026-08-13 用户决策：两者均保持现状，暂无数据）
4. **报告模板系统**：完善 Word/PDF 导出
5. **多用户支持**：会话数据按用户隔离
6. **安全加固**：输入校验、速率限制、认证授权
7. **配置外部化**：将 LLM 配置、各 MCP 服务账号凭据改为环境变量（2026-08-13 用户决策：暂缓，Mock 假凭据无需处理；接入真实接口时为必做项）
8. ~~**诊断日志优化**~~（2026-08-13 已完成冗余削减；不做归档/定期清理，用户决策）
9. **风向参数确认**：获取 wd 映射规则后恢复风偏工具的风向展示（2026-08-13 用户决策：暂缓，映射关系目前无法判断）

---

*本需求分析用于快速了解项目全貌。具体实现细节以源码为准。*
