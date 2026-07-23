# Task：PLDiagnosis 项目任务说明

> 本文档面向新加入的开发者或新的 Claude 对话实例，说明如何基于 PLDiagnosis 项目进行开发、修改和优化。
>
> 版本：0.2.0-alpha | 最后更新：2026-07-17

---

## Context（背景）

- **仓库定位**：基于 LLM 的输电线路故障综合诊断智能体，后端 Flask + 前端 Vue 3
- **当前状态**：雷电诊断工具已替换为真实数据服务并验证，新增 MCP 调用记录（覆盖写入 + 北京时间）与诊断全流程日志，`WeatherDiagnosisTool` 已通过提示词临时屏蔽以优化时延，其余工具仍为模拟数据
- **代码位置**：`/Users/yfzx/Desktop/Cluade_PLDiagonsis-master/`
- **相关外部依赖**：
  - 本地 LLM 服务：`http://172.18.179.2:20017/v1`
  - 特高压 Mock API：`http://localhost:8000`（雷电诊断数据源）
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
./start.sh dev
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
