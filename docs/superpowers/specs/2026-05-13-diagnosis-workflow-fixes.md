# 诊断流程修复设计文档

> **Goal:** 修复会话列表显示、诊断摘要一致性、策略排除逻辑等关键 bug。

---

## 问题清单

### 1. 会话列表显示"新会话"而非线路名
**根因:** 前端 `sessionStore.ts` 在 SSE 流中收到新 `session_id` 时硬编码 `line_name: '新会话'`。后端提取了正确线路名，但未通过 SSE 传递到前端。

**修复:** `Event.start` payload 携带 `line_name`，前端用其替换"新会话"。

### 2. 刷新后无法选中会话
**根因:** `SessionRepository.load_all()` 加载会话时，若 `DiagnosisResult.tool_name` 为 `None`，Pydantic 验证失败，会话被跳过（`continue`）。这是问题4的连锁反应。

**修复:** 修复问题4后，此问题自动解决。

### 3. "会话列表"改为"诊断列表"
**修复:** `SessionSidebar.vue` 文本替换。

### 4. 摘要显示"未知"但报告正确
**根因:** `MCPToolAdapter._mock_call()` 返回的模拟数据缺少 `fault_type` 和 `confidence` 字段。`ReportComposer._extract_summary()` 从 `structured_data` 提取这两个字段，取不到就回退到"未知"/0.0。

**修复:** 四个工具的 mock 数据加上 `fault_type` 和 `confidence`。

### 5. 策略排除逻辑缺陷
#### 5a. 多工具排除不支持
**根因:** `IntentClassifier` prompt 只要求单 `tool_name`，`ExcludeToolCommand` 只处理一个工具。

**修复:**
- Prompt 支持 `tool_names` 数组
- `ExcludeToolCommand` / `IncludeToolCommand` 循环处理多个工具
- `SessionManager` 加 `exclude_tools`/`include_tools` 批量方法

#### 5b. 连续排除不累积
**根因:** 实际测试确认 `session.excluded_tools` 是累积列表，连续排除应该已支持。若有问题，是 `PromptBuilder._build_overrides` 未正确渲染排除列表导致 LLM 未遵守。

**修复:** 在 `_build_overrides` 的 `已排除工具` 部分增加强调说明。

---

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `src/interfaces/web.py` | `Event.start` payload 加 `line_name` |
| `src/infrastructure/adapters/mcp_adapter.py` | mock 数据加 `fault_type`/`confidence` |
| `src/domain/intent_classifier.py` | prompt 支持多工具 |
| `src/application/commands/exclude.py` | 循环处理多工具 |
| `src/application/commands/include_tool.py` | 循环处理多工具 |
| `src/domain/session_manager.py` | 加批量 exclude_tools/include_tools |
| `src/domain/prompt_builder.py` | 排除工具强调说明 |
| `web/src/stores/sessionStore.ts` | 用 SSE payload 的 `line_name` |
| `web/src/components/SessionSidebar.vue` | "会话列表" → "诊断列表" |

---

## 测试计划

1. 发送"220kV武汉线 跳闸" → 会话列表显示"武汉线"
2. 刷新页面 → 会话仍存在且可点击
3. 诊断完成后 → 摘要 fault_type 与报告一致
4. 输入"去掉雷电和覆冰" → 两个工具都被排除，重新诊断时不再调用
5. 输入"去掉雷电"诊断，再"去掉覆冰"诊断 → 两次都基于累积的排除列表
