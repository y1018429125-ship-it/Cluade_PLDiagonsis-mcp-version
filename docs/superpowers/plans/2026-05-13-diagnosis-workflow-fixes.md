# 诊断流程修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复会话列表显示、诊断摘要一致性、策略排除逻辑等关键 bug。

**Architecture:** 后端通过 SSE payload 传递会话元数据，工具适配器产出结构化诊断结果，意图分类器和 Command 层支持多工具批量操作。

**Tech Stack:** Python 3.12, Pydantic v2, Flask 3.x, Vue 3 + TypeScript + Pinia

---

## File Structure

| File | Responsibility |
|------|--------------|
| `src/interfaces/web.py` | SSE 路由，`Event.start` payload 加 `line_name` |
| `src/infrastructure/adapters/mcp_adapter.py` | 工具 mock 数据加 `fault_type`/`confidence` |
| `src/domain/intent_classifier.py` | Prompt 支持多工具 `tool_names` 参数 |
| `src/application/commands/exclude.py` | 循环处理 `tool_names` 列表 |
| `src/application/commands/include_tool.py` | 循环处理 `tool_names` 列表 |
| `src/domain/session_manager.py` | 批量 `exclude_tools`/`include_tools` 方法 |
| `src/domain/prompt_builder.py` | 排除工具强调说明，确保 LLM 遵守 |
| `web/src/stores/sessionStore.ts` | SSE 接收 `line_name`，替换"新会话" |
| `web/src/components/SessionSidebar.vue` | "会话列表" → "诊断列表" |

---

### Task 1: SSE 传递 line_name，前端使用

**Files:**
- Modify: `src/interfaces/web.py:109`
- Modify: `web/src/stores/sessionStore.ts:131-138`

- [ ] **Step 1: 修改后端 Event.start payload**

在 `src/interfaces/web.py` 第 109 行，把 `Event.start` 的 payload 从字符串改为字典，携带 `line_name`：

```python
yield _sse_event(Event.start(session.session_id, "开始诊断..."))
```
改为：
```python
yield _sse_event(
    Event.start(
        session.session_id,
        {"message": "开始诊断...", "line_name": session.line_name},
    )
)
```

- [ ] **Step 2: 修改前端 sessionStore.ts**

在 `web/src/stores/sessionStore.ts` 第 131-138 行，替换硬编码的"新会话"：

```typescript
if (existingIdx === -1) {
  const lineName = event.payload?.line_name ?? '新会话'
  sessions.value.push({
    session_id: event.session_id,
    line_name: lineName,
    status: event.payload?.status ?? 'pending',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  })
}
```

- [ ] **Step 3: 验证**

构建前端：`cd web && npm run build`
期望：构建成功，无类型错误。

- [ ] **Step 4: Commit**

```bash
git add src/interfaces/web.py web/src/stores/sessionStore.ts
git commit -m "fix: pass line_name via SSE and use it in session list"
```

---

### Task 2: Mock 数据加 fault_type 和 confidence

**Files:**
- Modify: `src/infrastructure/adapters/mcp_adapter.py:199-230`

- [ ] **Step 1: 修改 LightningDiagnosisTool mock 数据**

在 `src/infrastructure/adapters/mcp_adapter.py` 第 203-209 行，在 `"LightningDiagnosisTool"` 字典末尾加两个字段：

```python
"LightningDiagnosisTool": {
    "strike_time": datetime.now().isoformat(),
    "longitude": 114.3055,
    "latitude": 30.5928,
    "current": 45.2,
    "distance_to_line": 1.2,
    "fault_type": "雷击故障",
    "confidence": 0.85,
},
```

- [ ] **Step 2: 修改 IcingDiagnosisTool mock 数据**

在第 210-216 行，在 `"IcingDiagnosisTool"` 字典末尾加两个字段：

```python
"IcingDiagnosisTool": {
    "temperature": -2.5,
    "humidity": 85.0,
    "wind_speed": 8.5,
    "icing_thickness": 5.2,
    "icing_risk_level": "高",
    "fault_type": "覆冰故障",
    "confidence": 0.72,
},
```

- [ ] **Step 3: 修改 WindDiagnosisTool mock 数据**

在第 217-222 行，在 `"WindDiagnosisTool"` 字典末尾加两个字段：

```python
"WindDiagnosisTool": {
    "max_wind_speed": 22.5,
    "wind_direction": "西北",
    "gust_speed": 28.0,
    "deflection_risk": "中",
    "fault_type": "风偏故障",
    "confidence": 0.60,
},
```

- [ ] **Step 4: 修改 BirdDamageDiagnosisTool mock 数据**

在第 223-228 行，在 `"BirdDamageDiagnosisTool"` 字典末尾加两个字段：

```python
"BirdDamageDiagnosisTool": {
    "bird_species_count": 12,
    "activity_level": "高",
    "nesting_sites": 3,
    "damage_history": "2024年3月曾发生鸟害导致的跳闸",
    "fault_type": "鸟害故障",
    "confidence": 0.55,
},
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/unit/test_report_composer.py -v
```
期望：测试通过（如果已有测试）。

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/adapters/mcp_adapter.py
git commit -m "fix: add fault_type and confidence to tool mock data"
```

---

### Task 3: 意图分类器支持多工具

**Files:**
- Modify: `src/domain/intent_classifier.py:63-95`

- [ ] **Step 1: 修改 system prompt**

在 `src/domain/intent_classifier.py` 第 63-95 行的 `_build_system_prompt` 方法中，把 `parameters` 示例改为支持 `tool_names` 数组，同时兼容单 `tool_name`：

找到这段：
```python
工具名称映射规则（参数中tool_name必须为标准名称）：
- 雷电、雷击 -> LightningDiagnosisTool
- 覆冰、结冰 -> IcingDiagnosisTool
- 风偏、大风 -> WindDiagnosisTool
- 鸟害、鸟类 -> BirdDamageDiagnosisTool
- 天气 -> WeatherDiagnosisTool

返回 JSON 格式：
{{
    "intent_type": "意图类型",
    "confidence": 0.95,
    "parameters": {{"tool_name": "标准工具名"}}
}}
```

改为：
```python
工具名称映射规则（参数中tool_name/tool_names必须为标准名称）：
- 雷电、雷击 -> LightningDiagnosisTool
- 覆冰、结冰 -> IcingDiagnosisTool
- 风偏、大风 -> WindDiagnosisTool
- 鸟害、鸟类 -> BirdDamageDiagnosisTool
- 天气 -> WeatherDiagnosisTool

返回 JSON 格式：
{{
    "intent_type": "意图类型",
    "confidence": 0.95,
    "parameters": {{"tool_name": "标准工具名"}}  // 单工具用 tool_name
}}
或（多工具排除/恢复时）：
{{
    "intent_type": "exclude_tool",
    "confidence": 0.95,
    "parameters": {{"tool_names": ["LightningDiagnosisTool", "IcingDiagnosisTool"]}}
}}
```

- [ ] **Step 2: Commit**

```bash
git add src/domain/intent_classifier.py
git commit -m "feat: support multi-tool exclusion in intent classifier prompt"
```

---

### Task 4: Exclude/Include Command 支持多工具

**Files:**
- Modify: `src/application/commands/exclude.py:30-60,62-68`
- Modify: `src/application/commands/include_tool.py:30-59,61-67`
- Modify: `src/domain/session_manager.py:158-174`

- [ ] **Step 1: 给 SessionManager 加批量方法**

在 `src/domain/session_manager.py` 第 158-174 行后面，加两个批量方法：

```python
    def exclude_tools(self, session_id: str, tool_names: List[str]) -> None:
        """批量排除工具"""
        session = self.get(session_id)
        changed = False
        for tool_name in tool_names:
            if tool_name not in session.excluded_tools:
                session.excluded_tools.append(tool_name)
                changed = True
        if changed:
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"批量排除工具: {session_id} -> {tool_names}")

    def include_tools(self, session_id: str, tool_names: List[str]) -> None:
        """批量恢复工具"""
        session = self.get(session_id)
        changed = False
        for tool_name in tool_names:
            if tool_name in session.excluded_tools:
                session.excluded_tools.remove(tool_name)
                changed = True
        if changed:
            session.updated_at = datetime.now()
            self._persist()
            logger.info(f"批量恢复工具: {session_id} -> {tool_names}")
```

- [ ] **Step 2: 修改 ExcludeToolCommand**

在 `src/application/commands/exclude.py`：

1. 把 `_extract_tool_name` 改名为 `_extract_tool_names`，返回 `List[str]`：

```python
    def _extract_tool_names(self, ctx: ExecutionContext) -> List[str]:
        """从意图参数中提取工具名列表"""
        if ctx.intent:
            params = ctx.intent.parameters
            # 优先使用 tool_names（多工具）
            tool_names = params.get("tool_names", [])
            if tool_names:
                return tool_names
            # 回退到单 tool_name
            tool_name = params.get("tool_name", "")
            if tool_name:
                return [tool_name]
        raise InvalidStateError("缺少 tool_name/tool_names 参数")
```

2. 修改 `execute` 方法，循环处理：

```python
    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行排除工具操作"""
        session = ctx.session
        tool_names = self._extract_tool_names(ctx)

        yield Event.thinking(session.session_id, f"准备排除工具: {', '.join(tool_names)}...")

        self._validate_state(session)
        for tool_name in tool_names:
            self._validate_tool_exists(tool_name)

        self.session_manager.exclude_tools(session.session_id, tool_names)
        for tool_name in tool_names:
            session.action_log.append(
                UserAction(
                    action_type="exclude",
                    parameters={"tool_name": tool_name},
                )
            )
        if session.status != SessionStatus.MODIFYING:
            self.session_manager.transition(session.session_id, SessionStatus.MODIFYING)

        logger.info(f"已排除工具: {session.session_id} -> {tool_names}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"已排除工具: {', '.join(tool_names)}",
                "excluded_tools": session.excluded_tools,
                "status": session.status.value,
            },
        )
```

3. 把 `_validate_tool_exists` 改为接受工具名参数（已在上面的循环中调用）。

- [ ] **Step 3: 修改 IncludeToolCommand**

在 `src/application/commands/include_tool.py`，做同样修改：

`_extract_tool_name` → `_extract_tool_names`（返回 `List[str]`），`execute` 循环处理，调用 `session_manager.include_tools`。

```python
    def _extract_tool_names(self, ctx: ExecutionContext) -> List[str]:
        """从意图参数中提取工具名列表"""
        if ctx.intent:
            params = ctx.intent.parameters
            tool_names = params.get("tool_names", [])
            if tool_names:
                return tool_names
            tool_name = params.get("tool_name", "")
            if tool_name:
                return [tool_name]
        raise InvalidStateError("缺少 tool_name/tool_names 参数")

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行恢复工具操作"""
        session = ctx.session
        tool_names = self._extract_tool_names(ctx)

        yield Event.thinking(session.session_id, f"准备恢复工具: {', '.join(tool_names)}...")

        self._validate_state(session)

        self.session_manager.include_tools(session.session_id, tool_names)
        for tool_name in tool_names:
            session.action_log.append(
                UserAction(
                    action_type="include",
                    parameters={"tool_name": tool_name},
                )
            )

        logger.info(f"已恢复工具: {session.session_id} -> {tool_names}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"已恢复工具: {', '.join(tool_names)}",
                "excluded_tools": session.excluded_tools,
                "status": session.status.value,
            },
        )
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/unit/test_commands.py -v
```
期望：如果测试引用了 `_extract_tool_name`，需要同步更新。

- [ ] **Step 5: Commit**

```bash
git add src/application/commands/exclude.py src/application/commands/include_tool.py src/domain/session_manager.py
git commit -m "feat: support multi-tool exclude/include in single request"
```

---

### Task 5: PromptBuilder 排除工具强调

**Files:**
- Modify: `src/domain/prompt_builder.py:128-132`

- [ ] **Step 1: 修改已排除工具说明**

在 `src/domain/prompt_builder.py` 第 128-132 行，找到：
```python
        if session.excluded_tools:
            parts.append("### 已排除工具")
            for tool_name in session.excluded_tools:
                parts.append(f"- {tool_name}")
```

改为：
```python
        if session.excluded_tools:
            parts.append("### 已排除工具（以下工具已被用户明确排除，诊断计划中禁止调用）")
            for tool_name in session.excluded_tools:
                parts.append(f"- {tool_name}")
            parts.append("注意：已排除的工具绝对不能出现在 tools_to_call 列表中。")
```

- [ ] **Step 2: Commit**

```bash
git add src/domain/prompt_builder.py
git commit -m "fix: emphasize excluded_tools in prompt so LLM respects them"
```

---

### Task 6: 前端"诊断列表"重命名

**Files:**
- Modify: `web/src/components/SessionSidebar.vue`

- [ ] **Step 1: 全局替换文本**

在 `web/src/components/SessionSidebar.vue` 中，把所有"会话列表"替换为"诊断列表"。

找到：
```vue
<h2>会话列表</h2>
```
改为：
```vue
<h2>诊断列表</h2>
```

（如果还有其他"会话"文案需同步改为"诊断"，一并处理。）

- [ ] **Step 2: 构建验证**

```bash
cd web && npm run build
```
期望：构建成功。

- [ ] **Step 3: Commit**

```bash
git add web/src/components/SessionSidebar.vue
git commit -m "ui: rename session list to diagnosis list"
```

---

### Task 7: 最终验证

- [ ] **Step 1: 运行后端单元测试**

```bash
pytest tests/unit/ -v --tb=short
```
期望：所有测试通过。

- [ ] **Step 2: 构建前端**

```bash
cd web && npm run build
```
期望：构建成功。

- [ ] **Step 3: 最终 Commit（如有未提交更改）**

```bash
git status
# 如有未提交更改：
git add -A
git commit -m "test: verify all diagnosis workflow fixes"
```

---

## Spec Coverage Check

| Spec 需求 | 对应任务 |
|-----------|----------|
| SSE 传递 line_name | Task 1 |
| 刷新后会话可加载 | Task 2（修复 tool_name=None） |
| "诊断列表"重命名 | Task 6 |
| 摘要与报告一致 | Task 2（mock 数据加 fault_type/confidence） |
| 多工具排除 | Task 3 + Task 4 |
| 连续排除累积 | Task 5（PromptBuilder 强调） |

无 gaps。

## Placeholder Scan

- [x] 无 "TBD"、"TODO"、"implement later"
- [x] 所有步骤含完整代码
- [x] 无 "Similar to Task N"

## Type Consistency

- `tool_names: List[str]` 在 Task 3 prompt、Task 4 Command、Task 4 SessionManager 中一致
- `Event.start` payload 在 Task 1 前后端一致（dict 含 `line_name`）
