# PLDiagnosis 项目总结

> 本文档汇总了 PLDiagnosis（输电线路故障综合诊断智能体）截至 2026-05-14 的实现状态、功能清单和核心工作流。
>
> 版本：0.2.0-alpha | 状态：模拟数据阶段

---

## 1. 项目概述

PLDiagnosis 是一个基于 LLM 的输电线路故障智能诊断系统。用户通过自然语言描述线路故障情况，系统调用多种诊断工具（雷电、覆冰、风偏、鸟害等），综合分析后生成标准化的诊断报告。系统支持人在回路（Human-in-the-Loop）交互，允许用户排除工具、调整权重、复查结果，并可将诊断策略保存为技能供后续复用。

### 1.1 核心特性

| 特性 | 说明 |
|------|------|
| 自然语言诊断 | 用户用自然语言描述故障，LLM 自动解析故障上下文 |
| 多工具协同诊断 | 雷电、覆冰、风偏、鸟害、天气等多种诊断工具并行/串行执行 |
| 权重引擎 | 基于工具权重和置信度计算综合诊断结果 |
| 人在回路 | 支持排除/恢复工具、调整权重、复查、修改报告 |
| 技能系统 | 诊断策略可保存为 Markdown 技能文件，后续直接加载 |
| 实时流式反馈 | SSE 流式传输诊断进度，前端实时展示 |
| 会话持久化 | 会话数据以 JSON 文件持久化，刷新页面不丢失 |
| 浏览器代理 | 集成 Playwright 浏览器代理，可抓取网页天气数据 |

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+, Flask |
| 数据验证 | Pydantic v2, pydantic-settings |
| LLM 接口 | OpenAI-compatible API (AsyncOpenAI) |
| 前端 | Vue 3.5 + TypeScript + Vite |
| 状态管理 | Pinia |
| 容器化 | Docker + docker-compose |
| 测试 | pytest, pytest-asyncio, pytest-cov |
| 代码规范 | black, ruff, mypy |
| CI/CD | GitHub Actions |

---

## 3. 架构设计

项目采用**分层架构**，带有六边形/整洁架构的影响：

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

### 3.1 关键架构决策

- **命令模式**：每个用户意图映射为一个 Command 类，统一接口 `execute(ctx) -> AsyncIterator[Event]`
- **依赖注入**：`Container` 类集中装配所有组件，避免手动传参
- **状态机**：会话状态转换受严格管控，非法转换会被拒绝
- **事件总线**：异步发布-订阅模式，解耦状态变更与事件通知
- **SSE 流式传输**：诊断进度实时推送到前端

---

## 4. 已实现功能

### 4.1 后端功能

#### 4.1.1 核心数据模型 (`src/core/models.py`)

| 模型 | 用途 |
|------|------|
| `FaultContext` | 故障上下文：线路名称、杆塔号、故障时间、天气、SCADA 数据、波形数据 |
| `ToolOutput` | 工具输出统一包装：原始文本、结构化数据、元数据 |
| `DiagnosisResult` | 单个工具的初步诊断结果：故障类型、置信度、证据 |
| `DiagnosisSummary` | 综合诊断摘要：主诊断、权重分布、被排除/复查的工具 |
| `DiagnosisSession` | 诊断会话：状态、权重、排除工具列表、历史摘要、聊天记录、操作日志 |
| `ExecutionContext` | 命令执行上下文：会话 + 故障上下文 + 用户消息 + 意图 |
| `Event` | SSE 事件：start/thinking/result/content/complete/error/status |
| `Strategy` | 保存的策略配置：权重、排除工具、模板名 |

#### 4.1.2 应用层命令 (`src/application/commands/`)

| 命令 | 功能 |
|------|------|
| `DiagnoseCommand` | 完整诊断流程：解析上下文 -> 加载技能 -> 规划诊断 -> 执行工具 -> 生成报告 -> 保存摘要 |
| `ExcludeToolCommand` | 将一个或多个工具加入排除列表，排除后自动触发重新诊断 |
| `IncludeToolCommand` | 将工具从排除列表中移除（恢复工具），恢复后自动触发重新诊断 |
| `RecheckToolCommand` | 重新执行指定工具，更新其输出，用权重引擎重新计算摘要 |
| `AdjustWeightCommand` | 调整工具权重（范围 0.1-2.0），可选重新计算摘要 |
| `CompleteDiagnosisCommand` | 将会话状态标记为 COMPLETED |
| `SaveStrategyCommand` | 将当前会话配置保存为 JSON 策略文件 |
| `SaveSkillCommand` | 将当前会话配置保存为 Markdown 技能文件 |

#### 4.1.3 领域层核心逻辑 (`src/domain/`)

| 组件 | 功能 |
|------|------|
| `StateMachine` | 会话状态机：PENDING -> DIAGNOSING -> MODIFYING -> COMPLETED，含 EXCLUDED/RECHECKING 分支 |
| `SessionManager` | 会话 CRUD、会话复用（同一线路同日期复用未完成的会话）、权重/排除工具管理 |
| `IntentClassifier` | 基于 LLM 的意图分类：13 种意图，支持工具名映射（雷电/覆冰/风偏/鸟害/天气），置信度低于 0.7 回退到 GENERAL |
| `DiagnosisPlanner` | 调用 LLM 生成 JSON 诊断计划（推理过程、要调用的工具、报告结构），支持流式输出 |
| `ToolExecutor` | 并行/串行执行诊断工具，错误隔离（一个工具失败不影响其他工具） |
| `WeightEngine` | 从工具结构化输出中提取置信度，按权重计算加权分数，确定主诊断 |
| `ReportComposer` | 单轮 LLM 调用生成完整 Markdown 诊断报告 |
| `ReportEngine` | 模板驱动的分章节报告生成（TABLE/TEXT/MIXED 三种渲染模式） |
| `PromptBuilder` | 组装完整 LLM 提示词：系统角色 + 技能指南 + 可用工具 + 会话覆盖（权重/排除工具）+ 用户输入 + 输出格式 |
| `SkillLoader` | 管理 `skills/` 目录下的 Markdown 技能文件，支持 CRUD 和内存缓存 |

#### 4.1.4 基础设施层 (`src/infrastructure/`)

| 组件 | 功能 |
|------|------|
| `SessionRepository` | JSON 文件持久化（`data/sessions.json`），原子写入（临时文件 + 替换） |
| `ToolRegistry` | 从 `config/tools/` 下的 YAML 文件加载工具配置，支持 MCP 和 Custom 适配器 |
| `MCPToolAdapter` | MCP 工具适配器：支持模拟模式（开发）和真实 HTTP MCP 客户端（生产） |
| `BrowserAgentAdapter` | 浏览器代理：Playwright + LLM 驱动，可浏览网页抓取天气数据 |
| `LLMService` | OpenAI API 包装：普通聊天、流式聊天、结构化输出（JSON + Pydantic 验证）、意图分类 |
| `FaultContextParser` | 基于规则的用户消息解析：线路名（含电压等级）、杆塔号、故障时间（多种格式）、天气信息、SCADA 数据、故障类型关键词 |
| `EventBus` | 内存发布-订阅事件总线，支持按事件类型和会话 ID 订阅 |

#### 4.1.5 Web API (`src/interfaces/web.py`)

**SSE 端点：**
- `POST /chat` — 主聊天接口，返回 SSE 流。流程：意图分类 -> 获取/创建会话 -> 构建执行上下文 -> 解析并执行命令 -> 流式返回事件

**REST 端点：**

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/sessions` | GET | 列出所有会话 |
| `/api/sessions/<id>` | GET | 获取会话详情（含聊天记录、操作日志、历史摘要） |
| `/api/sessions/<id>/switch` | POST | 切换当前活跃会话 |
| `/api/sessions/<id>/complete` | POST | 标记会话完成 |
| `/api/sessions/clear` | POST | 清空所有会话 |
| `/api/tools` | GET | 列出可用诊断工具 |
| `/api/settings` | GET | 获取默认权重、权重范围、LLM 配置 |
| `/api/settings/weights` | POST | 更新活跃会话的权重 |
| `/api/skills` | GET | 列出所有技能 |
| `/api/skills` | POST | 创建新技能 |
| `/api/skills/<name>/activate` | POST | 激活技能（设为当前会话默认） |
| `/api/skills/<name>` | DELETE | 删除技能 |
| `/api/skills/default` | GET/POST | 获取/设置全局默认技能 |
| `/api/skills/reset` | POST | 重置为默认策略 |
| `/api/skills/discover` | POST | 触发工具扫描 |
| `/api/sessions/<id>/skill-summary` | GET | 从会话操作日志生成技能摘要 |
| `/api/health` | GET | 健康检查 |

**静态文件：** 前端构建产物从 `web/dist` 通过 Flask 提供，SPA fallback 支持。

---

### 4.2 前端功能

#### 4.2.1 布局架构 (`App.vue`)

五栏水平布局，所有面板始终挂载：

```
┌─────────────┬─────────────────────┬─────────────┬─────────────┬─────────────┐
│  诊断列表    │      聊天面板        │   工具列表   │   报告预览   │  策略管理    │
│ (280px)     │    (flex: 1)        │  (260px)    │  (320px)    │  (280px)    │
└─────────────┴─────────────────────┴─────────────┴─────────────┴─────────────┘
```

#### 4.2.2 组件清单

| 组件 | 功能 |
|------|------|
| `SessionSidebar` | 会话列表：显示线路名、状态徽章（含脉冲动画）、电压等级、故障时间。点击切换会话。已完成会话禁用。支持刷新和清空。 |
| `ChatPanel` | 聊天主界面：消息渲染（start/thinking/complete/error/普通消息）、绿色摘要卡片、输入框（Enter 发送）、工具栏（显示轮数、清空对话）、自动滚动 |
| `ToolList` | 可用工具列表：显示工具名、分类徽章（电气/环境/生物/测试）、描述。只读展示。 |
| `ReportPreview` | 报告预览面板：渲染最新报告的 Markdown，显示"完成诊断"按钮，完成后可保存为新技能 |
| `ReportModal` | 全屏报告弹窗：通过"查看报告"触发，Teleport 到 body |
| `StrategyManager` | 技能管理：列出所有技能，激活/删除/重置操作，显示当前激活的技能 |

#### 4.2.3 状态管理 (`sessionStore.ts`)

Pinia Composition API 模式，核心状态：

| 状态 | 用途 |
|------|------|
| `sessions` | 所有会话列表 |
| `activeSessionId` | 当前活跃会话 ID |
| `messages` | 当前会话的聊天消息 |
| `isLoading` | SSE 流进行中（禁用输入） |
| `error` | 全局错误信息 |
| `reportModalVisible` | 报告弹窗显隐 |
| `currentReport` | 弹窗中的报告内容 |

核心 action：
- `loadSessions()` — 加载会话列表
- `selectSession(id)` — 切换会话，从后端恢复聊天记录和操作日志
- `postMessage(text)` — 发送用户消息，建立 SSE 连接，处理各类事件
- `markSessionComplete()` — 标记会话完成
- `clearAllSessions()` — 清空所有会话

#### 4.2.4 API 层

- `api/http.ts` — REST API 封装（标准 fetch + JSON）
- `api/sse.ts` — SSE 流客户端：返回 `AsyncGenerator<SSEEvent>`，内置 3 次重试逻辑

---

## 5. 核心工作流

### 5.1 端到端诊断流程

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
    │       │   └── 强调 excluded_tools，防止 LLM 规划已排除的工具
    │       ├── f. 诊断规划 (DiagnosisPlanner) ← LLM 流式输出
    │       ├── g. 执行工具 (ToolExecutor)
    │       │   └── 并行/串行调用工具，错误隔离
    │       ├── h. 生成报告 (ReportComposer) ← LLM 生成 Markdown
    │       ├── i. 计算摘要 (WeightEngine)
    │       └── j. 状态转入 MODIFYING
    │
    └── 5. SSE 流返回事件序列
        ├── event: start      → 前端显示"诊断中..."动画
        ├── event: thinking   → LLM 思考过程（前端不直接展示）
        ├── event: content    → 增量内容更新
        ├── event: status     → 会话状态更新（侧边栏同步）
        ├── event: complete   → 绿色摘要卡片（故障类型、置信度、操作日志）
        └── event: error      → 红色错误消息
```

### 5.2 人在回路交互流程

用户在诊断完成后（MODIFYING 状态）可以：

```
MODIFYING 状态
    │
    ├── 排除工具 ──> ExcludeToolCommand ──> 自动触发 DiagnoseCommand 重新诊断
    │                                    （累积排除：多次排除累加，不覆盖）
    ├── 恢复工具 ──> IncludeToolCommand ──> 自动触发 DiagnoseCommand 重新诊断
    │
    ├── 复查工具 ──> RecheckToolCommand ──> 重新执行该工具 + 重新计算摘要
    │
    ├── 调整权重 ──> AdjustWeightCommand ──> 更新权重 + 可选重新计算摘要
    │
    ├── 完成诊断 ──> CompleteDiagnosisCommand ──> 状态转入 COMPLETED
    │                                    └── 可选：保存为新技能
    │
    └── 继续对话 ──> 重新进入 DiagnoseCommand（修改报告）
```

### 5.3 技能保存与加载流程

```
完成诊断 (COMPLETED)
    │
    ├── 方式一：SaveSkillCommand
    │   └── 从会话的操作日志生成 Markdown 技能文件
    │       ├── 工具权重表
    │       ├── 排除/恢复历史
    │       └── 诊断策略描述
    │
    └── 方式二：前端点击"保存为新技能"
        └── 调用 /api/sessions/<id>/skill-summary
            └── 生成技能摘要 -> 用户命名 -> POST /api/skills 创建

加载技能
    └── 激活技能 (POST /api/skills/<name>/activate)
        └── 当前会话加载该技能的权重、排除工具等配置
```

### 5.4 前端用户交互流程

```
进入页面
    │
    ├── 加载会话列表 (GET /api/sessions)
    ├── 加载工具列表 (GET /api/tools)
    └── 加载技能列表 (GET /api/skills)
    │
    ▼
欢迎界面："输电线路故障综合诊断智能体"
    │
    ▼
用户输入故障描述并发送
    │
    ├── 前端：添加用户消息到 messages，添加空助手消息占位
    ├── 前端：建立 SSE 连接 (POST /chat)
    └── 后端：开始诊断流程...
    │
    ▼
SSE 事件驱动 UI 更新
    ├── start/thinking  → 显示"诊断中..."旋转动画
    ├── content/result  → 增量文本追加到助手消息
    ├── status          → 侧边栏会话状态实时更新
    └── complete        → 绿色摘要卡片 + 报告预览面板更新
    │
    ▼
用户查看报告
    ├── 点击"查看报告" → 弹出 ReportModal
    └── 右侧 ReportPreview 实时显示最新报告
    │
    ▼
用户交互（排除/恢复/复查/调整/完成）
    ├── 发送自然语言指令（如"排除覆冰诊断"）
    └── 后端识别意图 -> 执行对应命令 -> 自动重新诊断
    │
    ▼
完成诊断
    ├── 点击"完成诊断" → 状态变为 COMPLETED
    └── 可选：保存当前策略为新技能
```

---

## 6. 配置与数据

### 6.1 配置文件

| 文件 | 用途 |
|------|------|
| `config/config.yaml` | 应用主配置：LLM 参数、权重默认值、会话参数 |
| `config/tools/lightning.yaml` | 雷电诊断工具配置 |
| `config/tools/icing.yaml` | 覆冰诊断工具配置 |
| `config/tools/wind.yaml` | 风偏诊断工具配置 |
| `config/tools/bird.yaml` | 鸟害诊断工具配置 |
| `config/tools/weather.yaml` | 天气工具配置（浏览器代理） |
| `.env` / `.env.example` | 环境变量：LLM API 密钥、数据目录、前端路径 |

### 6.2 默认权重

| 工具 | 默认权重 |
|------|----------|
| 雷电诊断 (Lightning) | 1.0 |
| 覆冰诊断 (Icing) | 0.9 |
| 风偏诊断 (Wind) | 0.8 |
| 鸟害诊断 (Bird) | 0.6 |

---

## 7. 测试覆盖

### 7.1 测试统计

| 类型 | 文件数 | 测试函数数 |
|------|--------|-----------|
| 单元测试 | 32 | ~285 |
| 集成测试 | 1 | 5 |
| **合计** | **33** | **~290** |

### 7.2 主要测试覆盖区域

- **核心模型**：枚举值、边界校验、序列化反序列化
- **状态机**：所有合法/非法状态转换、各状态允许的命令
- **会话管理**：CRUD、复用语义、权重更新、工具排除/恢复
- **权重引擎**：权重校验（0.1-2.0）、加权计算、主诊断选择、置信度提取
- **意图分类**：分类返回、低置信度回退、异常回退
- **命令层**：所有命令的正常路径和错误路径
- **基础设施**：LLM 服务、事件总线、工具注册表、MCP 适配器、会话仓库、故障解析器
- **浏览器代理**：控制器、代理循环、动作执行器
- **Web API**：工具列表、会话详情、设置、技能接口

### 7.3 测试缺口

1. **无前端测试** — Vue 组件无单元测试或 E2E 测试
2. **Web API 覆盖不足** — 仅部分端点有测试，缺少聊天流、会话完成、技能激活等
3. **无性能/并发测试**
4. **无安全测试** — 输入校验、注入防护未专项测试
5. **ReportComposer 测试薄弱** — 仅 2 个测试

---

## 8. 设计文档索引

项目的设计文档位于 `docs/superpowers/`：

| 文档 | 内容 |
|------|------|
| `plans/2026-05-11-dynamic-skill-diagnosis-system.md` | 动态技能系统实现计划 |
| `plans/2026-05-12-ui-ux-improvements.md` | UI/UX 改进计划 |
| `plans/2026-05-13-diagnosis-workflow-fixes.md` | 诊断工作流修复计划 |
| `specs/2026-05-11-dynamic-skill-diagnosis-system-design.md` | 动态技能系统设计规格 |
| `specs/2026-05-12-ui-ux-improvements-design.md` | UI/UX 设计规格 |
| `specs/2026-05-13-diagnosis-workflow-fixes.md` | 工作流修复设计规格 |
| `specs/2025-05-11-weather-diagnosis-browser-agent-design.md` | 天气诊断浏览器代理设计 |

---

## 9. 入口点与启动

| 入口 | 路径 | 说明 |
|------|------|------|
| 后端服务 | `web_app.py` | Flask 服务，端口 5000 |
| 前端入口 | `web/src/main.ts` | Vue 3 SPA |
| 启动脚本 | `start.sh [dev\|docker]` | dev: 安装依赖 + 构建前端 + 运行 Flask；docker: docker-compose up |
| 构建产物 | `web/dist/` | Vite 构建输出，Flask 静态文件服务 |

---

## 10. 待办与后续方向

1. **前端测试**：补充 Vue 组件单元测试和 Playwright E2E 测试
2. **API 测试**：覆盖剩余 REST 端点，特别是聊天流和 SSE 事件
3. **真实 MCP 集成**：当前为模拟数据，需对接真实 MCP 服务
4. **报告模板系统**：`templates/` 目录目前为空，需完善 Word/PDF 导出
5. **多用户支持**：当前为单用户会话存储，需扩展到多用户隔离
6. **安全加固**：输入校验、速率限制、认证授权
