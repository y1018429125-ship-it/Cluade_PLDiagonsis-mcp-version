# 动态技能诊断系统设计文档

## 1. 概述

将诊断编排逻辑从硬编码 Python 流程中抽离，改为由大模型依据技能 Markdown 文件自主决策。用户可通过自然语言实时调整诊断策略，临时生效，满意后可保存为新技能文件。新工具安装后自动提示用户纳入诊断。

## 2. 背景与问题

当前系统痛点：
- `DEFAULT_WEIGHTS` 硬编码在 `src/core/models.py`
- 诊断流程固定：意图分类器 → 权重引擎 → 报告引擎
- 新增工具（如天气诊断）需修改代码才能接入诊断流程
- 策略/技能系统存在但简陋（仅支持 JSON 格式的激活/删除，无创建编辑界面）

## 3. 方案选择

**选定方案：A（纯 LLM 编排）**

理由：
- 用户明确需要"让大模型依据 md 看到的内容去决定"
- 条件逻辑（如"夏天跳过覆冰诊断"）用大模型推理比设计 DSL 更自然
- gemma-4-31B-it 模型能力足够支撑工具选择与报告生成
- 架构最简洁，无需维护并行的结构化解析器

## 4. 详细设计

### 4.1 Skill Markdown 格式

默认技能文件：`skills/comprehensive_diagnosis.md`

```markdown
# 输电线路综合诊断

## 描述
针对输电线路跳闸故障的综合诊断...

## 推荐工具配置

| 工具 | 权重 | 条件 |
|------|------|------|
| LightningDiagnosisTool | 1.0 | 始终调用 |
| IcingDiagnosisTool | 0.9 | 气温 ≤ 5°C 或冬季时调用 |
| WindDiagnosisTool | 0.8 | 始终调用 |
| BirdDamageDiagnosisTool | 0.6 | 始终调用 |

## 诊断流程

1. **信息提取**：从用户描述中提取线路名称、杆塔号、故障时间
2. **天气判断**：获取当前季节和天气，判断覆冰工具是否适用
3. **并行诊断**：同时调用所有符合条件的工具
4. **置信度计算**：结合权重和工具结果，计算各故障类型置信度
5. **报告生成**：按"报告结构"章节组织输出

## 报告结构

按以下顺序生成报告章节：
1. 概述
2. 故障分析
3. 诊断证据（每个工具的结果作为独立小节）
4. 诊断结论
5. 处理建议

## 注意事项

- 覆冰诊断仅在低温条件下有意义，夏季应主动跳过
- 如多个工具指向同一故障类型，应合并证据提升置信度
```

### 4.2 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| `SkillLoader` | `src/domain/skill_loader.py` | 加载 `skills/*.md`，缓存默认技能内容 |
| `PromptBuilder` | `src/domain/prompt_builder.py` | 组装给 LLM 的完整 prompt |
| `DiagnosisPlanner` | `src/domain/diagnosis_planner.py` | 调用 LLM 输出 JSON 诊断计划 |
| `ToolExecutor` | `src/domain/tool_executor.py` | 按计划并行/串行调用工具 |
| `ReportComposer` | `src/domain/report_composer.py` | 调用 LLM 一次性生成所有章节 |
| `SkillSaver` | `src/application/commands/save_skill.py` | 将会话调整持久化为新技能 MD |

### 4.3 诊断流程

```
用户输入: "武汉110kV线路跳闸"
         ↓
IntentClassifier → intent=DIAGNOSE
         ↓
DiagnoseCommand.execute(ctx)
         ↓
┌─────────────────┐
│ 1. SkillLoader  │ 加载 skills/comprehensive_diagnosis.md
└─────────────────┘
         ↓
┌─────────────────┐
│ 2. PromptBuilder│ 扫描 config/tools/*.yaml
│    扫描工具     │ 生成可用工具列表 + 新工具提示
└─────────────────┘
         ↓
┌─────────────────┐
│ 3. 组装 Prompt  │ system + skill + tools + overrides + user_msg
└─────────────────┘
         ↓
┌─────────────────┐
│ 4. DiagnosisPlanner│ 调用 LLM（第一次）
│    LLM 决策     │ 输出诊断计划 JSON
└─────────────────┘
         ↓
┌─────────────────┐
│ 5. ToolExecutor │ 并行调用 LLM 指定的工具
└─────────────────┘
         ↓
┌─────────────────┐
│ 6. ReportComposer│ 调用 LLM（第二次）
│    生成报告     │ 传入工具结果 → 输出报告
└─────────────────┘
         ↓
SSE 流式输出
```

**两次 LLM 调用设计**：
- 第一次：计划阶段，输出 JSON 决定调用哪些工具
- 第二次：报告阶段，一次性输出所有章节内容

### 4.4 Prompt 结构

```markdown
# 系统角色
你是输电线路故障诊断专家...

# 技能指南
{{ skill_markdown_content }}

# 可用工具目录
{{ available_tools_json }}

# 当前会话调整
{{ session_overrides }}

# 新工具提示（如有）
{{ new_tools_notice }}

# 用户输入
{{ user_message }}

# 输出要求
请输出诊断计划，严格 JSON 格式：
{
  "reasoning": "...",
  "tools_to_call": [
    {"name": "...", "rationale": "...", "parallel": true}
  ],
  "report_structure": ["概述", "故障分析", ...]
}
```

### 4.5 报告模板集成

- `TemplateParser` 不变，继续解析 `.docx` 提取章节结构
- `ReportEngine` 改造为 `ReportComposer`，一次性调用 LLM 生成所有章节
- LLM prompt 中包含模板章节结构，LLM 按此输出各章节内容
- 优先级：模板 > 技能 Markdown 默认 > 硬编码默认

### 4.6 动态工具发现

- 每次诊断前扫描 `config/tools/*.yaml`
- 对比当前技能提到的工具，检测新工具
- 新工具信息注入 prompt，LLM 自主提示用户

交互示例：
```
LLM: 💡 检测到新工具「天气诊断」可用...
     是否需要加入本次诊断？（您可以说"加入天气诊断"）

用户: 加入天气诊断
→ session.included_tools += ["WeatherDiagnosisTool"]
→ 下次诊断 LLM 将其纳入可用工具列表
```

### 4.7 自然语言调整

支持的调整指令：

| 用户说的话 | 系统动作 |
|-----------|---------|
| "把雷电权重改成 0.5" | session.active_weights["LightningDiagnosisTool"] = 0.5 |
| "不用覆冰诊断了" | session.excluded_tools += ["IcingDiagnosisTool"] |
| "加个历史对比章节" | session.report_overrides += {"add_chapter": "history"} |
| "先诊断雷电再诊断鸟害" | session.tool_order = [...] |

实现方式：将当前技能配置 + 用户指令发给 LLM，LLM 输出结构化调整 JSON。

### 4.8 保存技能

触发：用户说"保存为夏季诊断技能"

流程：
1. 收集当前会话所有调整（权重、排除/新增工具、报告结构变化）
2. 基于当前技能 Markdown 生成新版本
3. 更新工具表格权重、加入新工具、修改报告结构
4. 写入 `skills/<name>.md`

## 5. 数据模型变更

```python
class DiagnosisSession(BaseModel):
    # 现有字段保留
    active_weights: Dict[str, float]  # 用户临时调整，覆盖 skill 默认值
    excluded_tools: List[str]
    included_tools: List[str] = Field(default_factory=list)  # 新增：动态加入的工具
    report_overrides: Dict[str, Any] = Field(default_factory=dict)  # 新增：报告结构覆盖
    tool_order: Optional[List[str]] = None  # 新增：工具执行顺序覆盖
    active_skill_name: Optional[str] = None  # 新增：当前使用的技能名
```

## 6. 与现有系统兼容

| 现有组件 | 变更 |
|---------|------|
| `ToolRegistry` | 不变，继续加载/执行工具 |
| `StateMachine` | 不变，管理会话状态 |
| `IntentClassifier` | 简化，只做粗粒度路由 |
| `WeightEngine` | 保留做 fallback，主逻辑由 LLM 取代 |
| `ReportEngine` | 重构为 `ReportComposer` |
| `SaveStrategyCommand` | 重构为 `SaveSkillCommand`，输出 `.md` |

## 7. API 变更

新增/修改：
- `GET /api/skills` — 列出 `.md` 技能文件
- `POST /api/skills/<name>/activate` — 激活技能到当前会话
- `POST /api/skills` — 创建技能（接收 Markdown 内容）
- `DELETE /api/skills/<name>` — 删除技能
- `POST /api/skills/discover` — 手动触发工具扫描，返回新工具列表

## 8. 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| LLM 不输出合法 JSON | 添加重试逻辑 + fallback 到默认工具调用 |
| LLM 选择错误的工具 | 保留用户手动排除/加入工具的能力 |
| 两次 LLM 调用增加延迟 | 第一次计划调用可接受，第二次报告调用可流式输出 |
| 技能 Markdown 格式不统一 | 提供默认模板 + 验证器 |
