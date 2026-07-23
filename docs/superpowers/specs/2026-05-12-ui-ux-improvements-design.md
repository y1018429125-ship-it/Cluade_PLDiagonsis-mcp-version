# UI/UX 改进与诊断流程优化设计文档

> **日期**: 2026-05-12
> **范围**: 前端交互体验 + 后端诊断流程优化

---

## 背景

当前系统存在以下体验问题：
1. 诊断过程响应时间长，缺乏等待提示
2. 诊断完成后直接输出完整报告，淹没对话流
3. 排除/恢复工具后需手动触发重新诊断
4. 技能管理无默认激活，可多选
5. 切换会话后聊天面板为空，看不到历史结果
6. 完成诊断后无法保存诊断策略复用

---

## 设计目标

- **即时反馈**: 诊断过程中用户明确知道系统在忙及当前阶段
- **信息分层**: 摘要先行，详细报告按需查看
- **流程顺畅**: 排除/恢复后自动重新诊断
- **策略复用**: 诊断经验可保存为技能，下次套用

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                         前端 (Vue)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ ChatPanel    │  │ SessionSidebar│  │ ReportPreview    │  │
│  │ - 等待动画   │  │ - 脉冲状态   │  │ - 完成诊断按钮   │  │
│  │ - 摘要卡片   │  │ - 实时同步   │  │                  │  │
│  │ - 查看报告弹窗│  │               │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │ StrategyManager│  │ sessionStore (Pinia)               │ │
│  │ - 单选激活   │  │ - SSE 状态同步                     │ │
│  │ - 默认技能   │  │ - 摘要/报告分离存储               │ │
│  └──────────────┘  └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │ SSE / REST
┌─────────────────────────────────────────────────────────────┐
│                        后端 (Flask)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ web.py       │  │ StateMachine │  │ ReportComposer   │  │
│  │ - 自动重诊断 │  │ - status事件 │  │ - summary+report │  │
│  │ - 全局技能   │  │               │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ SessionManager│  │ SkillLoader  │  │ Commands         │  │
│  │ - 默认技能   │  │ - 默认comprehensive │  │ - 操作日志     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 详细设计

### 1. SSE 事件流增强 + 等待动画

#### 1.1 后端：状态变更 SSE 事件

在 `src/domain/state_machine.py` 的 `transition()` 方法中，状态转换时向 SSE 流发送 `status` 事件：

```python
# 新增事件类型 EventType.STATUS = "status"
# 转换完成后发送:
Event.status(session.session_id, {"status": target.value})
```

同时，`DiagnoseCommand` 执行过程中，`thinking` 事件增加 `phase` 字段标识当前阶段：

```python
Event.thinking(session.session_id, "正在分析故障原因...", phase="planning")
Event.thinking(session.session_id, "正在查询天气数据...", phase="executing")
Event.thinking(session.session_id, "正在生成诊断报告...", phase="composing")
```

#### 1.2 前端：增强等待动画

`ChatPanel.vue` 中，`thinking` 状态的消息气泡增强为阶段动画：

- 显示脉冲圆点 + 阶段文字（如"正在分析故障原因..."）
- 阶段变化时平滑过渡

`SessionSidebar.vue` 中，`diagnosing` 状态的 badge 增加 CSS 脉冲动画：

```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.status-diagnosing {
  animation: pulse 1.5s ease-in-out infinite;
}
```

#### 1.3 前端：会话列表实时状态同步

`sessionStore.ts` 的 SSE 循环中，新增 `status` 事件处理：

```typescript
} else if (event.event_type === 'status') {
  const newStatus = event.payload?.status
  const idx = sessions.value.findIndex(s => s.session_id === event.session_id)
  if (idx !== -1) {
    sessions.value[idx].status = newStatus
  }
}
```

---

### 2. 诊断报告摘要 + 模态框查看

#### 2.1 后端：结构化诊断输出

`ReportComposer` 生成诊断结果时，同时产出两份内容：

```python
class DiagnosisResult:
    summary: dict  # {fault_type: str, confidence: float}
    report: str    # 完整 Markdown 报告
```

SSE `complete` 事件 payload 结构：

```json
{
  "event_type": "complete",
  "session_id": "sess_xxx",
  "payload": {
    "summary": {
      "fault_type": "雷击故障",
      "confidence": 0.92
    },
    "report": "# 诊断报告\n...",
    "message": "诊断完成"
  }
}
```

#### 2.2 前端：摘要卡片

`sessionStore.ts` 中，`complete` 事件处理更新：

```typescript
} else if (event.event_type === 'complete') {
  assistantMsg.summary = event.payload?.summary
  assistantMsg.report = event.payload?.report
  assistantMsg.content = event.payload?.message || '诊断完成'
}
```

`ChatPanel.vue` 中，`complete` 事件的消息气泡显示摘要卡片：

```
┌─────────────────────────────┐
│  诊断完成                    │
│  ─────────────────────────  │
│  故障类型：雷击故障          │
│  置信度：92%                │
│  ─────────────────────────  │
│  [查看报告]  [完成诊断]     │
└─────────────────────────────┘
```

#### 2.3 前端：模态框查看完整报告

新增 `ReportModal.vue` 组件：

- 点击"查看报告"按钮时弹出
- 展示完整 Markdown 报告内容
- 支持关闭（点击遮罩或 X 按钮）

```vue
<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click="close">
      <div class="modal-content" @click.stop>
        <header>
          <h3>诊断报告</h3>
          <button @click="close">&times;</button>
        </header>
        <div class="modal-body markdown-body" v-html="renderMarkdown(report)" />
      </div>
    </div>
  </Teleport>
</template>
```

---

### 3. 排除/恢复后自动重新诊断

#### 3.1 后端：无条件自动链式诊断

修改 `src/interfaces/web.py` 的 `_chat_stream` 函数：

```python
# 当前逻辑（需要关键词）:
# if intent_type in (IntentType.EXCLUDE_TOOL, IntentType.INCLUDE_TOOL):
#     if "再次诊断" in message or "重新诊断" in message:
#         ...

# 新逻辑（无条件）:
if intent_type in (IntentType.EXCLUDE_TOOL, IntentType.INCLUDE_TOOL):
    yield _sse_event(
        Event.thinking(session.session_id, "自动重新诊断...")
    )
    diagnose_cmd = DiagnoseCommand(...)
    async for event in diagnose_cmd.execute(ctx):
        yield _sse_event(event)
```

用户说"去掉覆冰"、"排除覆冰"、"恢复雷电"等命令后，系统自动排除/恢复工具，然后立即重新诊断并输出新的摘要报告。

---

### 4. 技能默认激活 + 单选机制

#### 4.1 后端：全局默认技能配置

`Container` 增加全局默认技能字段：

```python
class Container:
    def __init__(self):
        ...
        self.default_skill_name: str = "comprehensive_diagnosis"
```

`SessionManager.get_or_create()` 中，创建会话时自动继承：

```python
session.active_skill_name = self._default_skill_name
```

新增 API 路由：

```python
@app.route("/api/skills/default", methods=["GET"])
def get_default_skill():
    return jsonify({
        "default_skill": container.default_skill_name,
        "available_skills": container.skill_loader.list_skills()
    })

@app.route("/api/skills/default", methods=["POST"])
def set_default_skill():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "技能名称不能为空"}), 400
    if name not in container.skill_loader.list_skills():
        return jsonify({"error": f"技能 '{name}' 不存在"}), 404
    container.default_skill_name = name
    return jsonify({"success": True, "default_skill": name})
```

#### 4.2 前端：单选激活 UI

`StrategyManager.vue`：

- 页面加载时调用 `GET /api/skills/default` 获取当前默认技能
- 点击"激活"按钮调用 `POST /api/skills/default`，前端即时更新选中状态（单选）
- 已激活技能显示"已激活"，其他显示"激活"
- `comprehensive_diagnosis` 首次加载时默认显示为已激活

---

### 5. 切换会话时显示最新诊断结果

#### 5.1 后端：扩展会话详情 API

`GET /api/sessions/<id>` 扩展返回内容，增加 `latest_summary`：

```json
{
  "session_id": "sess_xxx",
  "line_name": "武汉线跳闸 2026-5-12 08:50",
  "status": "modifying",
  "latest_summary": {
    "fault_type": "雷击故障",
    "confidence": 0.92,
    "report": "# 完整报告..."
  }
}
```

#### 5.2 前端：切换会话后恢复聊天记录

`sessionStore.ts` 的 `selectSession` 中：

```typescript
async function selectSession(sessionId: string) {
  try {
    error.value = null
    const data = await switchSession(sessionId)
    if (data.success) {
      activeSessionId.value = sessionId
      messages.value = []
      
      // 如果有最新摘要，插入到聊天中
      if (data.latest_summary) {
        messages.value.push({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '诊断完成',
          eventType: 'complete',
          summary: data.latest_summary,
          report: data.latest_summary.report,
          timestamp: new Date().toISOString(),
        })
      }
    }
  } catch (err) {
    error.value = (err as Error).message
  }
}
```

---

### 6. 完成诊断后保存为新技能

#### 6.1 后端：操作历史记录

`DiagnosisSession` 的 `action_log` 字段记录用户操作：

```python
# 已有字段: action_log: List[dict] = field(default_factory=list)

# ExcludeToolCommand 执行时:
session.action_log.append({
    "type": "exclude",
    "tool_name": tool_name,
    "timestamp": datetime.now().isoformat(),
})

# IncludeToolCommand 执行时:
session.action_log.append({
    "type": "include",
    "tool_name": tool_name,
    "timestamp": datetime.now().isoformat(),
})

# AdjustWeightCommand 执行时:
session.action_log.append({
    "type": "adjust_weight",
    "tool_name": tool_name,
    "weight": new_weight,
    "timestamp": datetime.now().isoformat(),
})
```

#### 6.2 后端：生成技能摘要 API

```python
@app.route("/api/sessions/<id>/skill-summary", methods=["GET"])
def generate_skill_summary(id: str):
    session = container.session_manager.get(id)
    
    excluded = set()
    included = set()
    weight_changes = {}
    report_modifications = []
    
    for action in session.action_log:
        t = action["type"]
        if t == "exclude":
            excluded.add(action["tool_name"])
        elif t == "include":
            included.add(action["tool_name"])
        elif t == "adjust_weight":
            weight_changes[action["tool_name"]] = action["weight"]
        elif t == "modify_report":
            report_modifications.append(action["description"])
    
    final_excluded = excluded - included  # 去重：排除后又恢复的不保留
    
    content = f"""# {session.line_name} 诊断策略

## 描述
基于 {session.line_name} 的诊断经验自动生成的策略模板。
适用于类似故障场景的输电线路诊断。

## 默认排除的诊断工具
{chr(10).join(f"- {t}" for t in final_excluded) or "无"}

## 默认权重调整
{chr(10).join(f"- {t}: {v}" for t, v in weight_changes.items()) or "无"}

## 报告模板修改
{chr(10).join(f"- {m}" for m in report_modifications) or "无"}

## 使用说明
激活此技能后，新会话将自动应用上述配置。
"""
    suggested_name = f"{session.line_name}_策略"
    return jsonify({"content": content, "suggested_name": suggested_name})
```

#### 6.3 前端：保存技能询问流程

`ReportPreview.vue` 中，点击"完成诊断"后：

```typescript
async function handleComplete() {
  await store.markSessionComplete()
  
  // 弹出询问框
  const saveSkill = confirm('是否将此诊断策略保存为新技能？')
  if (saveSkill) {
    const data = await getSkillSummary(sessionId)
    const name = prompt('技能名称:', data.suggested_name)
    if (name) {
      await createSkill(name, data.content)
      alert(`技能 "${name}" 已保存`)
    }
  }
}
```

#### 6.4 技能应用逻辑

激活技能后，新创建会话时自动应用技能中的配置：

```python
# SessionManager.get_or_create() 中
if session.active_skill_name and session.active_skill_name != "comprehensive_diagnosis":
    skill_content = container.skill_loader.load(session.active_skill_name)
    # 解析技能内容，提取排除列表和权重调整
    # 应用到 session.excluded_tools 和 session.active_weights
```

---

## 数据流图

### 诊断流程（含自动重诊断）

```
用户输入: "去掉覆冰"
    ↓
意图识别: EXCLUDE_TOOL
    ↓
ExcludeToolCommand 执行 → 排除工具 → 记录 action_log
    ↓
自动链式触发 DiagnoseCommand
    ↓
状态: modifying → diagnosing (发送 status 事件)
    ↓
诊断执行 (thinking 事件带 phase)
    ↓
状态: diagnosing → modifying (发送 status 事件)
    ↓
ReportComposer 生成 summary + report
    ↓
SSE complete 事件: {summary, report}
    ↓
前端: 显示摘要卡片 (含"查看报告"、"完成诊断"按钮)
```

### 完成诊断 + 保存技能流程

```
用户点击: "完成诊断"
    ↓
POST /api/sessions/{id}/complete
    ↓
状态: modifying → completed
    ↓
前端询问: "是否保存为新技能？"
    ↓
用户确认
    ↓
GET /api/sessions/{id}/skill-summary
    ↓
后端汇总 action_log（去重）→ 生成 Markdown
    ↓
POST /api/skills (保存为新技能)
    ↓
技能列表更新，可激活使用
```

---

## API 变更清单

| 方法 | 路径 | 变更 |
|------|------|------|
| GET | `/api/sessions/<id>` | 新增返回 `latest_summary` 字段 |
| POST | `/api/skills/default` | 新增：设置全局默认技能 |
| GET | `/api/skills/default` | 新增：获取全局默认技能 |
| GET | `/api/sessions/<id>/skill-summary` | 新增：生成技能摘要 |
| SSE | `status` | 新增事件类型 |
| SSE | `complete` | payload 结构变更 |

---

## 前端组件变更清单

| 组件 | 变更 |
|------|------|
| `ChatPanel.vue` | thinking 动画增强，complete 显示摘要卡片 |
| `SessionSidebar.vue` | diagnosing 脉冲动画，实时状态同步 |
| `ReportPreview.vue` | 完成诊断后询问保存技能 |
| `StrategyManager.vue` | 单选激活，获取默认技能 |
| `sessionStore.ts` | SSE 处理 status/complete，切换会话恢复摘要 |
| **新增** `ReportModal.vue` | 模态框展示完整报告 |

---

## 后端文件变更清单

| 文件 | 变更 |
|------|------|
| `src/domain/state_machine.py` | transition 发送 status SSE 事件 |
| `src/domain/session_manager.py` | get_or_create 继承默认技能 |
| `src/application/commands/exclude.py` | 记录 action_log |
| `src/application/commands/include_tool.py` | 记录 action_log |
| `src/application/commands/adjust_weight.py` | 记录 action_log |
| `src/application/commands/complete_diagnosis.py` | 询问保存技能（前端处理） |
| `src/interfaces/web.py` | 新增 API 路由，自动重诊断逻辑 |
| `src/core/models.py` | 确认 EventType.STATUS 存在 |

---

## 风险与注意事项

1. **SSE 格式变更**: `complete` 事件 payload 结构变化，前端需同步适配
2. **状态同步延迟**: SSE status 事件可能丢失，前端仍需定时刷新会话列表作为兜底
3. **技能 Markdown 解析**: 技能应用时需要解析 Markdown 内容提取配置，建议后续改为结构化 YAML frontmatter
4. **操作日志持久化**: `action_log` 目前随会话持久化到 JSON，大量操作可能影响性能

---

## 待后续优化

- 技能文件使用 YAML frontmatter 存储结构化配置（更便于解析）
- 诊断进度百分比（当前只有阶段文字）
- 报告模板上传和选择（任务 #48）
