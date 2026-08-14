# Task：PLDiagnosis 项目任务说明

> 本文档面向新加入的开发者或新的 Claude 对话实例，说明如何基于 PLDiagnosis 项目进行开发、修改和优化。
>
> 版本：0.2.0-alpha | 最后更新：2026-08-12

---

## Context（背景）

- **仓库定位**：基于 LLM 的输电线路故障综合诊断智能体，后端 Flask + 前端 Vue 3
- **当前状态**：雷电/气象/风偏三个 MCP 工具已接入真实 getWeather/Trip 数据（各用独立账号 YFZX-1/2/3，并行无 token 竞争）；气象（温湿度+湿度描述）与风偏（风速+阈值描述，10 m/s）仅输出语言描述，加权章节按 0 × 1.0 = 0 呈现；风向 wd 弃用（映射规则未确认）；鸟害工具已注册表级禁用（诊断与前端均不可见）；覆冰工具仍为模拟数据、按季节/温度跳过；报告 LaTeX 清洗器与诊断全流程日志已上线验证（日志已瘦身：thinking 合并单条 + images 占位符，单次约 21KB）；"历史关联"功能已上线（答案随会话持久化至 sessions.json，跨刷新/重启秒开；知识库地址在 config/config.yaml 的 knowledge_base.base_url）；**报告已改为流式输出（2026-08-14，REPORT_CHUNK 逐字推进，感知时延 2-3s 出首字；历史关联预取与报告生成并行）**；`./start.sh` 一键重启全部前后端服务
- **代码位置**：`/Users/yfzx/Desktop/Cluade_PLDiagonsis-master/`
- **相关外部依赖**：
  - 本地 LLM 服务：`http://172.18.179.2:20017/v1`
  - 特高压 Mock API：`http://localhost:8000`（雷电诊断数据源）
  - 故障知识库 API：`http://localhost:8503`（历史关联数据源，POST /query {question} → {answer}）
- **已读关键文档**：
  - `requirements.md`（需求分析）
  - `docs/project-summary.md`（项目总结）
  - `config/config.yaml`（主配置）
  - `修改.md`（修改记录）

---

## Goal（目标）

让新开发者或新 Claude 实例能够快速：

1. 理解项目结构和核心工作流
2. 定位需要修改的代码位置
3. 按规范进行开发、测试和验证
4. 安全地集成新的 MCP 工具或修改现有智能体行为

---

## Acceptance criteria（验收标准）

- [ ] 新开发者阅读本文档后，能在 10 分钟内定位任意功能对应的代码文件
- [ ] 所有代码修改必须提供验证命令和实际输出
- [ ] 涉及 MCP 工具接入的修改必须通过 `skills/mcp-security-check.md` 审查
- [ ] 涉及编码的修改必须遵循 `skills/coding-protocol.md` 的 Scout → Builder → Verifier 流程
- [ ] 涉及 Word/PDF/Excel/Skill/MCP Server 的任务必须先读取对应 SKILL.md
- [ ] 涉及诊断日志相关改动时，需验证 `logs/diagnosis/<date>/` 下 JSON 输出完整
- [ ] 不泄露 secrets（.env、key、token、credentials）
- [ ] 改动超过 5 个文件时必须停下说明理由
- [ ] 连续 2 次排错失败找不到原因时必须停下报告

---

## Constraints（约束）

### 1. 开发规范

- **编码任务**：必须执行 `skills/coding-protocol.md`
  - Scout → Builder → Verifier 质量流程
  - 长任务（> 3 个文件）自动触发 `skills/ulw-loop.md`
- **MCP 相关**：必须执行 `skills/mcp-security-check.md`
- **技术研究文档**：按双层结构输出（User-Facing Conceptual Layer + Agent-Facing Technical Layer）
- **文档与 Skill 管理**：必须先读取对应 SKILL.md
  - Word：`.docx` → `skills/docx/SKILL.md`
  - PDF：→ `skills/pdf/SKILL.md`
  - Excel/CSV：→ `skills/xlsx/SKILL.md`
  - Skill 创建/修改：→ `skills/skill-creator/SKILL.md`
  - MCP Server 开发：→ `skills/python-mcp-server-generator/SKILL.md`

### 2. 安全红线

- 任何情况都不许泄露 secrets
- 禁止读取或传播敏感配置文件
- MCP 工具接入前必须完成安全审查

### 3. 最小改动原则

- 不重构无关代码
- 不添加未要求的配置或功能
- 改动超过 5 个文件需停下说明理由

### 4. start.sh 启动脚本维护规则（2026-08-14 用户要求）

**原则**：`start.sh` 只管进程编排（杀端口、起服务、构建前端、健康检查），不知道也不关心代码内容。日常修改任何现有代码/配置/skill 文件都**不需要**动它。

**以下结构性变化发生时，必须主动提醒用户"本次改动需要同步更新 start.sh"，说明要改哪一处，经用户确认后再改**：

| 触发场景 | start.sh 需改动处 |
|----------|------------------|
| 新增/下线 MCP 工具服务 | 杀端口列表、启动列表、健康检查列表 |
| 某服务端口变更 | 对应端口号 |
| 服务启动方式变化（入口文件、环境变量、venv 等） | `start_service` 函数或对应启动命令 |
| 前端构建命令变化 | 第 3 步构建命令 |
| 后端入口/启动方式变化 | 第 4 步 Flask 启动命令 |

**不纳入 start.sh**：故障知识库（localhost:8503）为独立项目，有自己的启动脚本，不由此脚本启动（2026-08-14 用户确认）。

**相关但不同的判断——改代码后是否需要重启**（无需改 start.sh，但影响验证方式）：
- 后端 Python / skill 文件 / config.yaml → 重启 Flask（无热更新，SkillLoader 有进程内缓存）
- 前端 Vue/TS → `npm run build` + 浏览器强制刷新（无需重启 Flask）
- 单个 MCP 服务代码 → 只重启该服务
- 不确定时直接 `./start.sh` 全量重启

---

## 常见任务速查

### 1. 修改某个 MCP 工具的输出

| 步骤 | 操作 |
|------|------|
| 定位 | `mcp-services/<tool>-service/main.py` |
| 模型 | `mcp-services/<tool>-service/models.py` |
| 测试 | `mcp-services/<tool>-service/test_main.py` |
| 配置 | `config/tools/<tool>.yaml` |
| 验证 | `curl http://localhost:<port>/health` 和 `curl -X POST http://localhost:<port>/diagnose` |

### 2. 修改 LLM 调用行为

| 文件 | 用途 |
|------|------|
| `src/infrastructure/llm_service.py` | LLM 服务封装 |
| `src/domain/prompt_builder.py` | Prompt 组装 |
| `src/domain/report_composer.py` | 报告生成 |
| `src/domain/report_sanitizer.py` | 报告 LaTeX 清洗（`$...$` → 纯文本，报告入库前必经过） |
| `src/domain/diagnosis_planner.py` | 诊断规划 |
| `config/config.yaml` | LLM 参数配置 |

### 3. 修改诊断工作流或会话状态

| 文件 | 用途 |
|------|------|
| `src/application/commands/diagnose.py` | 主诊断命令 |
| `src/domain/state_machine.py` | 状态机 |
| `src/domain/session_manager.py` | 会话管理 |
| `src/domain/tool_executor.py` | 工具执行 |
| `src/infrastructure/diagnosis_logger.py` | 诊断全流程日志 |

### 4. 修改前端

| 文件 | 用途 |
|------|------|
| `web/src/App.vue` | 主布局 |
| `web/src/components/ChatPanel.vue` | 聊天面板 |
| `web/src/components/SessionSidebar.vue` | 会话列表 |
| `web/src/components/ToolList.vue` | 工具列表 |
| `web/src/components/ReportPreview.vue` | 报告预览 |
| `web/src/components/StrategyManager.vue` | 策略/技能管理 |
| `web/src/stores/sessionStore.ts` | 全局状态（含前端日志发送） |
| `web/src/api/http.ts` | REST API 封装 |
| `web/src/api/sse.ts` | SSE 流封装 |

### 5. 新增 MCP 工具

| 步骤 | 操作 |
|------|------|
| 1 | 在 `mcp-services/` 下新建 `<tool>-service/` 目录 |
| 2 | 创建 `main.py`、`models.py`、`requirements.txt`、`Dockerfile`、`test_main.py` |
| 3 | 实现 `/health` 和 `/diagnose` 接口 |
| 4 | 在 `config/tools/` 下新建 `<tool>.yaml` |
| 5 | 更新 `start.sh` 启动该服务 |
| 6 | 执行 `skills/mcp-security-check.md` |
| 7 | 运行测试并验证 |

---

## 验证命令

### 启动项目

```bash
cd /Users/yfzx/Desktop/Cluade_PLDiagonsis-master
./start.sh
```

### 单独验证 MCP 服务

```bash
cd mcp-services/lightning-service
python3 -m pytest test_main.py -v -c /dev/null
```

```bash
curl -s http://localhost:8001/health
curl -s -X POST http://localhost:8001/diagnose \
  -H 'Content-Type: application/json' \
  -d '{"line_name":"雅湖线","fault_time":"2025-05-08T19:46:30"}'
```

### 运行后端测试

```bash
cd /Users/yfzx/Desktop/Cluade_PLDiagonsis-master
python3 -m pytest
```

### 语法检查

```bash
cd /Users/yfzx/Desktop/Cluade_PLDiagonsis-master
python3 -m py_compile web_app.py
python3 -m py_compile src/**/*.py
```

### 诊断日志验证

```bash
# 在前端发起一次诊断后检查日志
ls -la logs/diagnosis/$(date +%Y-%m-%d)
python3 -m json.tool logs/diagnosis/$(date +%Y-%m-%d)/<latest>.json | head -50
```

---

## Delivery（必须交付）

任何修改任务完成后，必须交付：

1. **修改说明**：改了什么、为什么、影响范围
2. **关键 diff**：影响最大的改动
3. **验证输出**：实际执行的命令和完整输出
4. **遗留问题**：未解决的边界或待优化点
5. **更新 `修改.md`**：将本次修改追加到项目修改记录
6. **同步 `requirements.md` / `task.md`**：如新增功能或修改关键行为，同步更新需求和任务文档

---

## 附加说明

### 编码规范

- 严格遵守 `skills/coding-protocol.md` 的质量流程
- 长任务按 `skills/ulw-loop.md` 切成多轮
- 每轮结束必须有验证日志

### 沟通规范

- 执行任何工具操作前，先用中文说明并征求用户同意
- 用户输入 "1" 时，暂停工作，简要报告状态并询问是否继续
- 用户要求回答问题前，先分析根因，再给出方案，由用户决策后执行

### 参考资料

| 文档 | 位置 |
|------|------|
| 项目需求分析 | `requirements.md` |
| 修改记录 | `修改.md` |
| 会话交接 | `temp.md` |
| 项目总结 | `docs/project-summary.md` |
| 编码协议 | `skills/coding-protocol.md` |
| MCP 安全审查 | `skills/mcp-security-check.md` |
| 研究文档标准 | `skills/research-doc-standard.md` |

---

*本任务说明用于指导后续开发工作。具体执行时请结合当前对话上下文和项目实际状态。*
