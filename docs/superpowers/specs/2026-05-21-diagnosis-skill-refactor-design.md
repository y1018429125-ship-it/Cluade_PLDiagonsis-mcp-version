# 输电线路故障诊断系统 — Skill 体系重构设计文档

## 1. 背景与目标

### 1.1 现状问题

当前诊断系统存在以下问题：

1. **时间精度丢失**：用户输入 `2026-5-12 08:00:05.013`，系统只能显示为 `2026-5-12 08:00:00`，毫秒级信息在全链路丢失
2. **权重规则硬编码**：`weight_engine.py` 和 `report_composer.py` 中硬编码 `confidence * weight` 计算，LLM 不理解规则，无法自主判断
3. **Skill 格式不标准**：`comprehensive_diagnosis.md` 无 YAML frontmatter，无触发机制，无法自动路由
4. **模板系统缺失**：用户无法上传自定义报告模板（Word/PDF），报告结构硬编码
5. **报告修改不灵活**：用户无法以自然语言方式交互式修改报告内容

### 1.2 设计目标

1. **纯 Skill 驱动**：诊断规则（加权算法、工具调用策略、报告结构）全部写入 Skill 文件，LLM 自主理解执行
2. **时间精确到毫秒**：全链路支持毫秒级时间戳，显示格式固定为 `YYYY-MM-DD HH:MM:SS.mmm`
3. **Agent Skill 规范**：采用 Claude Code 原生 Skill 格式（YAML frontmatter + pushy description）
4. **多格式模板支持**：支持上传 Word(.docx)、PDF(.pdf)、Markdown(.md) 模板，解析为 LLM 可读的 Markdown 参考文档
5. **交互式报告修改**：用户以自然语言指令修改报告，LLM 自主理解并调整

---

## 2. 核心设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 权重计算位置 | 从代码迁移到 Skill | 用户明确选择"纯 Skill 驱动"，LLM 读取 Skill 后自主计算 |
| Skill 格式 | Claude Code 原生格式（YAML frontmatter） | 支持自动路由，description 作为触发机制 |
| 模板解析输出 | Markdown（非 JSON） | LLM 天然可读，人类可直接编辑，与 Skill 体系兼容 |
| 模板格式支持 | .md / .docx / .pdf | 覆盖真实业务场景，Word 和 PDF 是实际工作模板的主要来源 |
| 报告修改方式 | 全量重写（基于指令） | 保持报告一致性，避免局部修改导致逻辑断裂 |
| Skill 扩展模式 | 独立 Skill + 共享 References | 通用规则抽离复用，新诊断场景只需写独立 Skill |

---

## 3. 详细设计

### 3.1 时间格式修复（全链路）

#### 3.1.1 正则增强（`fault_parser.py`）

当前正则：
```python
re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?")
```

增强后：
```python
re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{3}))?")
```

解析逻辑增加毫秒：
```python
second = int(groups[5]) if groups[5] else 0
millisecond = int(groups[6]) if groups[6] else 0
return datetime(year, month, day, hour, minute, second, millisecond * 1000)
```

#### 3.1.2 序列化统一

- 后端所有时间字段序列化使用：`dt.isoformat(timespec='milliseconds')` → `2026-05-12T08:00:05.013`
- 前端接收 ISO 格式，显示时转换：
  ```typescript
  function formatTime(iso: string): string {
    const d = new Date(iso);
    const pad = (n: number) => n.toString().padStart(2, '0');
    const ms = d.getMilliseconds().toString().padStart(3, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${ms}`;
  }
  ```

#### 3.1.3 影响点

| 文件 | 修改内容 |
|------|---------|
| `fault_parser.py:38` | 正则增加毫秒捕获组 `(?:\.(\d{3}))?` |
| `fault_parser.py:159` | 解析微秒：`microsecond = int(groups[6]) * 1000` |
| `report_composer.py:123` | 报告中的时间使用固定格式 |
| `web/src/components/SessionSidebar.vue:81` | 替换 `toLocaleString()` 为固定格式函数 |
| `core/models.py` | Pydantic 时间序列化配置 `json_encoders` |

---

### 3.2 Skill 体系重构

#### 3.2.1 目录结构

```
skills/
├── comprehensive_diagnosis.md          # 主诊断 Skill
├── report_template_parser.md           # 模板解析 Skill
├── report_modifier.md                  # 报告修改 Skill
└── references/
    ├── diagnosis_rules.md              # 通用诊断规则（加权算法）
    ├── report_structure.md             # 通用报告结构规范
    └── tool_guidelines.md              # 工具调用通用规范
```

#### 3.2.2 `comprehensive_diagnosis.md`（重写）

```markdown
---
name: comprehensive_diagnosis
description: |
  输电线路跳闸故障综合诊断专家。当用户描述输电线路故障、跳闸、
  线路异常、杆塔问题、雷击、覆冰、风偏、鸟害等情况时，必须使用此技能。
  即使用户没有明确说"诊断"，只要涉及线路名称+故障/异常/跳闸/闪络/
  接地/短路等关键词，都应自动触发此技能。
  适用于 220kV/500kV/750kV/1000kV 等各电压等级输电线路。
---

# 输电线路综合诊断

## 核心算法：加权置信度

所有工具返回的结果都有置信度（confidence，0~1 之间）。
你必须按以下公式计算每个工具的加权置信度：

```
加权置信度 = 工具返回的 confidence × 该工具的 weight
```

最终按加权置信度从高到低排序，最高者对应的故障类型为主要原因。
如果两个工具加权置信度差距 < 0.1，则列为并列主要原因。

## 工具权重配置

```yaml
weights:
  LightningDiagnosisTool: 1.0
  IcingDiagnosisTool: 0.9
  WindDiagnosisTool: 0.8
  BirdDamageDiagnosisTool: 0.6
```

## 工具调用策略

| 工具 | 权重 | 调用条件 |
|------|------|---------|
| LightningDiagnosisTool | 1.0 | 始终调用 |
| IcingDiagnosisTool | 0.9 | 气温 ≤ 5°C 或冬季时调用，否则主动跳过 |
| WindDiagnosisTool | 0.8 | 始终调用 |
| BirdDamageDiagnosisTool | 0.6 | 始终调用 |

## 诊断流程

1. **信息提取**：从用户描述中提取线路名称、杆塔号、故障时间（精确到毫秒）
2. **天气判断**：获取当前季节和天气，判断覆冰工具是否适用
3. **并行诊断**：同时调用所有符合条件的工具
4. **加权计算**：对每个工具结果计算 加权置信度 = confidence × weight
5. **排序判断**：按加权置信度降序排列，最高者为主要原因
6. **报告生成**：按激活模板的章节结构组织输出

## 置信度等级划分

- HIGH（高置信度）：加权置信度 ≥ 0.7
- MEDIUM（中置信度）：加权置信度 0.4 ~ 0.7
- LOW（低置信度）：加权置信度 < 0.4

## 注意事项

- 覆冰诊断仅在低温条件下有意义，夏季应主动跳过
- 如多个工具指向同一故障类型，应合并证据提升置信度
- 新增工具可用时，应提示用户是否纳入本次诊断
- 故障时间必须精确到毫秒，格式为 YYYY-MM-DD HH:MM:SS.mmm
```

#### 3.2.3 `references/diagnosis_rules.md`（新增）

```markdown
# 通用诊断规则

## 加权置信度算法

这是所有诊断技能共享的核心排序算法：

```
加权置信度 = 工具返回的 confidence × 该工具的 weight
```

## 主要原因判定

按加权置信度从高到低排序，取最高者为主要原因（primary_diagnosis）。
如果两个工具加权置信度差距 < 0.1，则列为并列主要原因。

## 置信度等级

- HIGH：≥ 0.7
- MEDIUM：0.4 ~ 0.7
- LOW：< 0.4

## 工具调用原则

1. 尊重用户的排除/包含指令
2. 根据气象条件判断工具是否适用
3. 并行调用所有符合条件的工具
4. 每个工具的结果都要纳入加权计算
```

#### 3.2.4 `references/report_structure.md`（新增）

```markdown
# 通用报告结构规范

## 默认章节顺序

1. 概述
2. 故障分析
3. 诊断证据
4. 诊断结论
5. 处理建议

## 章节内容要求

- 概述：简要描述故障概况，包括线路名称、故障时间（精确到毫秒）、故障类型
- 故障分析：结合气象数据和历史记录分析故障原因
- 诊断证据：按工具分类列出详细诊断结果，包含每个工具的置信度和加权置信度
- 诊断结论：明确判定主要原因、次要原因，给出加权置信度排序
- 处理建议：给出具体的运维和检修建议

## 格式要求

- 使用 Markdown 格式
- 一级标题为报告总标题
- 二级标题为各章节
- 诊断结论中必须列出加权置信度计算过程
```

#### 3.2.5 `references/tool_guidelines.md`（新增）

```markdown
# 工具调用通用规范

## 输出格式期望

每个诊断工具应返回以下结构：

```json
{
  "fault_type": "雷击",
  "confidence": 0.85,
  "evidence": ["证据1", "证据2"],
  "details": {...}
}
```

## 置信度含义

- 0.9~1.0：几乎确定
- 0.7~0.9：高度可能
- 0.4~0.7：有一定可能
- 0.1~0.4：可能性较低
- 0~0.1：几乎不可能

## 调用原则

- 并行调用所有符合条件的工具
- 不等待单一工具结果再做下一步判断
- 所有工具结果一视同仁纳入加权计算
```

---

### 3.3 模板系统（多格式上传）

#### 3.3.1 存储结构

```
templates/
├── default.md                      # 系统默认模板（Markdown）
├── uploads/                        # 用户上传的原始文件
│   ├── 国网标准模板.docx
│   ├── 省公司模板.pdf
│   └── 自定义模板.md
└── parsed/                         # 解析后的 Markdown（LLM 可读）
    ├── 国网标准模板.md
    ├── 省公司模板.md
    └── 自定义模板.md
```

#### 3.3.2 解析策略

| 格式 | 解析工具 | 章节识别 | 说明提取 |
|------|---------|---------|---------|
| .md | 正则文本解析 | `##` 二级标题 | 方括号 `[章节说明：xxx]` |
| .docx | `python-docx` | paragraph.style.name in ('Heading 1', 'Heading 2', 'Heading 3') | 标题后的段落文本 |
| .pdf | `pdfplumber` 提取文本 + LLM 辅助 | LLM 识别章节边界 | 段落分组后提取说明 |

#### 3.3.3 解析后 Markdown 格式

```markdown
# 国网标准模板

> 来源文件：国网标准模板.docx
> 解析时间：2026-05-21 10:30:05.013
> 原始格式：docx

## 报告标题

输电线路故障诊断报告

## 章节结构

### 第1章：概述
- **内容指导**：简要描述故障概况，包括线路名称、故障时间、故障类型
- **原始位置**：第1页，Heading 1

### 第2章：故障分析
- **内容指导**：分析故障原因，结合气象数据和历史记录
- **原始位置**：第1页，Heading 2

### 第3章：诊断证据
- **内容指导**：按工具分类列出详细诊断结果
- **原始位置**：第2页，Heading 2

### 第4章：诊断结论
- **内容指导**：明确判定主要原因和次要原因，必须列出加权置信度计算过程
- **原始位置**：第2页，Heading 2

### 第5章：处理建议
- **内容指导**：给出具体的运维和检修建议
- **原始位置**：第3页，Heading 2
```

#### 3.3.4 `report_template_parser.md`（新增）

```markdown
---
name: report_template_parser
description: |
  报告模板解析器。当用户上传模板文件（.md/.docx/.pdf）、
  切换激活模板、或需要理解当前模板章节结构时触发。
  支持从 Word、PDF、Markdown 中提取章节标题、顺序和内容指导。
  解析结果保存为 Markdown 格式，供报告生成时作为参考注入。
---

# 报告模板解析

## 支持格式

- Markdown (.md)：解析 ## 标题和 [章节说明] 标记
- Word (.docx)：解析 Heading 1/2/3 样式标题及后续段落
- PDF (.pdf)：提取文本后识别章节边界

## 解析输出

统一输出为 Markdown 格式的章节结构文档，保存到 templates/parsed/ 目录。
输出必须包含：报告标题、章节列表（含顺序、标题、内容指导、原始位置）
```

#### 3.3.5 模板激活机制

| 层级 | 存储位置 | 说明 |
|------|---------|------|
| 全局默认 | `templates/default.md` | 无激活模板时的 fallback |
| 会话级 | `session.active_template_name` | 每个会话独立激活一个模板 |
| 单次覆盖 | 用户指令"用XX模板诊断" | 本次诊断临时指定 |

**激活流程**：
1. 用户上传文件 → 保存到 `templates/uploads/` → 触发解析 → 生成 `templates/parsed/<name>.md`
2. 用户激活模板 → 系统检查 `.md` 是否存在，不存在则先解析
3. 报告生成时，`ReportComposer` 读取 `templates/parsed/<active>.md` 注入 prompt

#### 3.3.6 新增模块

| 模块 | 类型 | 职责 |
|------|------|------|
| `TemplateUploadHandler` | Handler | 接收上传文件，保存到 `templates/uploads/` |
| `TemplateParser`（基类） | ABC | 定义统一解析接口 `parse(source_path) -> str` |
| `MarkdownTemplateParser` | 实现 | 解析 .md 文件 |
| `DocxTemplateParser` | 实现 | `python-docx` 解析 .docx |
| `PdfTemplateParser` | 实现 | `pdfplumber` + LLM 解析 .pdf |
| `TemplateRegistry` | 服务 | 管理模板列表、激活状态、解析缓存 |
| `TemplateActivateCommand` | Command | 激活/切换模板，只能激活一个 |

#### 3.3.7 API 设计

```
POST /templates/upload         # 上传模板文件
GET  /templates/list           # 列出所有模板（含解析状态）
POST /templates/activate       # 激活指定模板（body: {template_name}）
DELETE /templates/{name}       # 删除模板（同时删 uploads/ 和 parsed/）
GET  /templates/{name}/parsed  # 查看解析结果
```

---

### 3.4 交互式报告修改

#### 3.4.1 用户指令类型

| 类型 | 示例 |
|------|------|
| 删除内容 | "删除第一章关于天气的描述" |
| 增加内容 | "在结论里加上对雷击概率的评估" |
| 修改内容 | "把第二章的诊断证据部分加点数据支撑" |
| 调整结构 | "把处理建议放到结论前面" |
| 重写章节 | "重新写概述，突出故障时间" |
| 调整语气 | "结论写得更确定一些" |

#### 3.4.2 `report_modifier.md`（新增）

```markdown
---
name: report_modifier
description: |
  报告修改专家。当用户在诊断期间要求修改报告内容时触发。
  包括但不限于：删除某章节内容、增加分析、调整结构、重写段落、
  修改措辞等。用户可能用自然语言描述修改意图，你需要精确理解并执行。
---

# 报告修改

## 修改原则

1. **精确理解**：仔细分析用户指令的真实意图，不猜测不臆断
2. **保持完整**：不删除用户未要求删除的内容
3. **逻辑连贯**：修改后报告整体逻辑必须通顺
4. **格式一致**：保持 Markdown 格式，章节层级不变（除非用户要求调整结构）
5. **专业准确**：修改后的内容必须专业、准确、符合电力行业规范

## 修改类型处理

### 删除
- 精确定位用户提到的章节/段落
- 只删除目标内容，保留上下文衔接

### 增加
- 在指定位置插入新内容
- 保持与前后文的风格和逻辑一致

### 修改
- 替换目标内容
- 保留原有结构框架

### 结构调整
- 按用户要求的顺序重新排列章节
- 确保章节编号和引用同步更新
```

#### 3.4.3 `ModifyReportCommand` 改造

```python
async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
    session = ctx.session
    current_report = session.latest_report
    
    # 1. 读取当前激活模板（作为约束）
    template_md = self._load_active_template(session)
    
    # 2. 构建修改提示词
    prompt = f"""
你是输电线路故障诊断报告编辑专家。

## 当前报告
{current_report}

## 用户修改指令
{ctx.user_message}

## 模板约束（必须遵守的章节结构）
{template_md}

## 修改要求
1. 严格理解用户意图，精确执行修改
2. 保持报告的专业性和逻辑连贯性
3. 不删除用户未要求删除的内容
4. 修改后报告必须符合模板章节结构
5. 如果用户要求调整章节顺序，在保持内容完整的前提下重新组织

请输出修改后的完整报告。
"""
    
    # 3. LLM 生成修改后报告
    modified_report = await self.llm.chat([
        {"role": "system", "content": "你是输电线路故障诊断报告编辑专家。"},
        {"role": "user", "content": prompt},
    ])
    
    # 4. 记录修改操作
    self.session_manager.add_action(
        session.session_id,
        action_type="modify_report",
        parameters={
            "instruction": ctx.user_message,
            "before_length": len(current_report),
            "after_length": len(modified_report),
        }
    )
    
    # 5. 更新报告
    session.latest_report = modified_report
    
    yield Event.complete(session.session_id, {
        "report": modified_report,
        "message": "报告已按您的要求修改",
    })
```

---

### 3.5 用户诊断交互动作

诊断不是一次性完成的，用户在诊断过程中可以持续与系统交互，调整诊断策略和报告内容。所有用户操作都记录到 `session.action_log` 中，用于后续保存为新 Skill。

#### 3.5.1 动作清单

| 动作 | 用户指令示例 | 作用 | 影响的状态 | 可用状态 |
|------|-------------|------|-----------|---------|
| **排除工具** | "排除鸟害诊断" / "不要考虑鸟害" | 将工具加入 `excluded_tools`，后续诊断不再调用 | `excluded_tools` | diagnosing, modifying |
| **恢复工具** | "恢复鸟害诊断" / "把鸟害加回来" | 从 `excluded_tools` 移除，恢复调用 | `excluded_tools` | modifying |
| **调整权重** | "把雷击权重调到1.2" / "提高覆冰权重" | 修改 `active_weights` 中指定工具的权重 | `active_weights` | modifying |
| **重新检查** | "重新查一下雷击" / "再跑一次风偏" | 清除指定工具的缓存，强制重新调用 | `tool_outputs_cache`, `rechecked_tools` | modifying |
| **修改报告** | "结论写得更确定一些" / "删除关于鸟害的描述" | LLM 基于指令重写报告 | `latest_report` | modifying |
| **切换模板** | "用国网模板重新生成" / "换成标准模板" | 更换 `active_template_name`，重新生成报告 | `active_template_name` | modifying |
| **保存技能** | "保存当前配置为新技能" / "把这个策略存下来" | 将当前配置持久化为 Skill 文件 | `skills/*.md` | modifying |
| **完成诊断** | "完成诊断" / "结束" | 标记会话为已完成，可触发保存技能 | `status` → completed | modifying |

#### 3.5.2 动作交互流程

```
用户输入自然语言指令
    │
    ▼
IntentClassifier 识别意图
    │
    ├── "排除XX" ──→ ExcludeToolCommand
    │       ├── 验证工具存在
    │       ├── 加入 session.excluded_tools
    │       └── 记录 action_log
    │
    ├── "恢复XX" ──→ IncludeToolCommand
    │       ├── 从 excluded_tools 移除
    │       └── 记录 action_log
    │
    ├── "调整权重" ──→ AdjustWeightCommand
    │       ├── 验证权重范围 [0.1, 2.0]
    │       ├── 更新 session.active_weights
    │       └── 记录 action_log
    │
    ├── "重新检查XX" ──→ RecheckToolCommand
    │       ├── 清除 tool_outputs_cache[tool_name]
    │       ├── 重新调用工具
    │       ├── 更新 session.rechecked_tools
    │       └── 记录 action_log
    │
    ├── "修改报告..." ──→ ModifyReportCommand
    │       ├── 读取 current_report
    │       ├── 读取 active_template（约束）
    │       ├── 加载 report_modifier.md
    │       ├── LLM 理解指令 → 重写报告
    │       ├── 更新 session.latest_report
    │       └── 记录 action_log
    │
    ├── "切换模板" ──→ ActivateTemplateCommand
    │       ├── 验证模板存在且已解析
    │       ├── 更新 session.active_template_name
    │       └── 记录 action_log
    │
    ├── "保存技能" ──→ SaveSkillCommand
    │       ├── 收集 session 状态：
    │       │   ├── active_weights
    │       │   ├── excluded_tools
    │       │   ├── active_template_name
    │       │   ├── action_log（用户操作历史）
    │       │   └── latest_report 结构
    │       ├── 生成符合 Agent Skill 规范的 Markdown
    │       ├── 保存到 skills/<name>.md
    │       └── 更新 session.active_skill_name
    │
    └── "完成诊断" ──→ CompleteDiagnosisCommand
            ├── 记录 action_log
            ├── 状态 → COMPLETED
            └── 提示用户"是否保存当前配置为新技能？"
```

#### 3.5.3 动作状态机

```
PENDING ──[开始诊断]──→ DIAGNOSING ──[诊断完成]──→ MODIFYING
                                                         │
                    ┌─────────────────────────────────────┘
                    │ 用户交互动作（排除/恢复/调权重/重新检查/修改报告/切换模板）
                    │ 动作执行后仍回到 MODIFYING
                    │
                    ▼
              MODIFYING ──[完成诊断]──→ COMPLETED
```

**关键规则：**
- 所有调整动作只能在 `MODIFYING` 状态执行（诊断完成后）
- `EXCLUDED` 和 `RECHECKING` 是临时过渡状态，动作完成后自动回到 `MODIFYING`
- 完成诊断后会话冻结，不可再修改

---

### 3.6 诊断完成后保存新技能

#### 3.6.1 保存时机与触发

| 触发方式 | 说明 |
|---------|------|
| **自动提示** | 用户点击"完成诊断"后，系统自动询问"是否将当前诊断策略保存为新技能？" |
| **主动指令** | 用户在 MODIFYING 状态说"保存当前配置为XX技能" |
| **批量保存** | 支持将多个历史会话的最佳实践合并为一个通用技能（进阶功能） |

#### 3.6.2 保存内容

保存时从当前会话提取以下信息，生成符合 Agent Skill 规范的 Markdown 文件：

| 来源字段 | 生成到 Skill 的哪个部分 |
|---------|----------------------|
| `session.line_name` + `fault_context` | Description（触发条件补充） |
| `session.active_weights` | YAML frontmatter `weights` + 工具权重配置表 |
| `session.excluded_tools` | 排除工具列表（生成调用条件"跳过XX"） |
| `session.active_template_name` | 报告结构引用（关联模板） |
| `session.action_log` | 诊断流程优化建议（根据用户频繁操作推断偏好） |
| `session.custom_strategy_name` | Skill 名称（用户指定或自动生成） |

#### 3.6.3 生成 Skill 的格式规范

保存的 Skill 必须完全符合 Agent Skill 规范：

1. **YAML frontmatter**：`name` + `description`（pushy，包含触发条件）
2. **核心算法章节**：明确写出加权置信度计算规则
3. **工具配置**：从会话实际使用的工具生成，含权重和调用条件
4. **诊断流程**：基于 action_log 中的操作历史优化流程步骤
5. **报告结构**：引用当前激活模板的章节结构

#### 3.6.4 生成 Skill 样例

假设用户诊断了"220kV京西线雷击故障"，过程中：
- 排除了 BirdDamageDiagnosisTool
- 将 LightningDiagnosisTool 权重调到 1.2
- 将 IcingDiagnosisTool 权重降到 0.5
- 使用"国网标准模板"

点击"完成诊断"后保存为 `lightning_priority_diagnosis.md`：

```markdown
---
name: lightning_priority_diagnosis
description: |
  雷击优先型输电线路故障诊断。当用户描述输电线路跳闸、
  雷击、雷电、闪络等情况时，必须使用此技能。
  特别适用于有明显雷击迹象的故障场景（如雷暴天气、
  杆塔接地异常、绝缘子闪络等）。
  即使用户没有明确说"雷击"，只要故障时间附近有雷暴天气
  或线路位于雷击高发区，都应优先触发此技能。
  适用于 220kV/500kV/750kV/1000kV 等各电压等级输电线路。
---

# 雷击优先型输电线路故障诊断

## 核心算法：加权置信度

所有工具返回的结果都有置信度（confidence，0~1 之间）。
你必须按以下公式计算每个工具的加权置信度：

```
加权置信度 = 工具返回的 confidence × 该工具的 weight
```

最终按加权置信度从高到低排序，最高者对应的故障类型为主要原因。
如果两个工具加权置信度差距 < 0.1，则列为并列主要原因。

## 工具权重配置

```yaml
weights:
  LightningDiagnosisTool: 1.2
  WindDiagnosisTool: 0.8
  IcingDiagnosisTool: 0.5
  BirdDamageDiagnosisTool: 0.6
```

## 工具调用策略

| 工具 | 权重 | 调用条件 |
|------|------|---------|
| LightningDiagnosisTool | 1.2 | **优先调用**，雷击高发区或雷暴天气时权重提升 |
| WindDiagnosisTool | 0.8 | 始终调用 |
| IcingDiagnosisTool | 0.5 | 仅在气温 ≤ 0°C 且湿度 > 80% 时调用，优先级降低 |
| BirdDamageDiagnosisTool | 0.6 | **跳过**，本策略不关注鸟害因素 |

## 诊断流程

1. **信息提取**：提取线路名称、杆塔号、故障时间（精确到毫秒）、雷暴天气记录
2. **雷击优先判断**：检查故障时间附近是否有雷暴活动、线路是否在雷击高发区
3. **并行诊断**：调用所有符合条件的工具（跳过鸟害）
4. **加权计算**：对每个工具结果计算 加权置信度 = confidence × weight
5. **雷击确认**：若 LightningDiagnosisTool 加权置信度最高，重点分析雷击证据
6. **报告生成**：按激活模板的章节结构组织输出

## 置信度等级划分

- HIGH（高置信度）：加权置信度 ≥ 0.7
- MEDIUM（中置信度）：加权置信度 0.4 ~ 0.7
- LOW（低置信度）：加权置信度 < 0.4

## 注意事项

- 本策略优先排查雷击，但不排除其他故障类型
- 覆冰诊断在本策略中优先级较低，仅在严寒条件下调用
- 鸟害诊断被排除，如用户要求可考虑恢复
- 故障时间必须精确到毫秒，格式为 YYYY-MM-DD HH:MM:SS.mmm
- 报告结论中必须明确列出每个工具的加权置信度计算过程
- 特别关注：雷暴天气数据、接地电阻异常、绝缘子状态

## 历史优化记录

本技能由以下诊断实践生成：
- 来源会话：220kV京西线雷击故障诊断
- 用户调整：提升雷击权重至1.2，排除鸟害诊断，降低覆冰权重
- 生成时间：2026-05-21 10:30:05.013
```

#### 3.6.5 SaveSkillCommand 改造

```python
class SaveSkillCommand(Command):
    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        session = ctx.session
        skill_name = self._extract_skill_name(ctx)
        
        # 收集会话完整状态
        skill_config = {
            "name": skill_name,
            "line_context": session.line_name,
            "weights": session.active_weights.copy(),
            "excluded_tools": session.excluded_tools.copy(),
            "included_tools": session.included_tools.copy(),
            "template_name": session.active_template_name,
            "action_history": [
                {"type": a.action_type, "params": a.parameters, "time": a.timestamp.isoformat()}
                for a in session.action_log
            ],
        }
        
        # 使用 LLM 生成符合 Agent Skill 规范的 Markdown
        prompt = self._build_skill_generation_prompt(skill_config)
        skill_md = await self.llm_service.chat([
            {"role": "system", "content": "你是 Skill 生成专家。将诊断配置转换为符合规范的 Markdown Skill 文件。"},
            {"role": "user", "content": prompt},
        ])
        
        # 保存到 skills/ 目录
        file_path = self._save_to_file(skill_name, skill_md)
        
        # 更新会话
        session.active_skill_name = skill_name
        
        yield Event.complete(session.session_id, {
            "message": f"技能 '{skill_name}' 已保存",
            "skill_name": skill_name,
            "file_path": str(file_path),
        })
    
    def _build_skill_generation_prompt(self, config: dict) -> str:
        return f"""
请根据以下诊断配置，生成一个符合 Agent Skill 规范的 Markdown 文件。

## 配置信息

- 技能名称：{config['name']}
- 线路上下文：{config['line_context']}
- 激活模板：{config['template_name']}

### 工具权重配置
```yaml
{yaml.dump({'weights': config['weights']})}
```

### 排除的工具
{chr(10).join(f"- {t}" for t in config['excluded_tools']) or "无"}

### 用户操作历史
{chr(10).join(f"- {a['type']}: {a['params']}" for a in config['action_history'])}

## 生成要求

1. YAML frontmatter 必须包含 name 和 description（description 要 pushy，明确触发条件）
2. 必须包含"核心算法：加权置信度"章节，明确写出计算公式
3. 工具调用策略表必须反映排除的工具（标记为"跳过"或说明条件）
4. 诊断流程必须基于用户操作历史优化
5. 注意事项中体现用户的偏好设置
6. 末尾添加"历史优化记录"章节，说明本技能的来源

请直接输出 Markdown 内容，不要添加代码块标记。
"""
```

---

## 4. 完整系统架构

```
用户输入
  │
  ├── 上传模板 ───────────────────────────────┐
  │     │                                      │
  │     ▼                                      │
  │  TemplateUploadHandler                     │
  │     ├── 保存原始文件到 templates/uploads/   │
  │     └── 触发 TemplateParser                │
  │           │                                │
  │           ├── .md ──→ MarkdownParser       │
  │           ├── .docx ──→ DocxParser         │
  │           └── .pdf ──→ PdfParser           │
  │                 │                          │
  │                 ▼                          │
  │           统一输出 Markdown                │
  │           保存到 templates/parsed/          │
  │                                            │
  ├── 激活模板 ──→ TemplateRegistry.activate() │
  │                 更新 session.active_template│
  │                 只能激活一个                │
  │                                            │
  ├── 诊断意图 ──→ IntentClassifier            │
  │                 │                          │
  │                 ▼                          │
  │              SkillLoader 自动路由          │
  │                 │                          │
  │                 ▼                          │
  │              comprehensive_diagnosis.md    │
  │                 │                          │
  │                 ├── 引用 references/        │
  │                 │   ├── diagnosis_rules.md  │
  │                 │   ├── report_structure.md │
  │                 │   └── tool_guidelines.md  │
  │                 │                          │
  │                 └── LLM 自主决策            │
  │                        │                   │
  │                        ▼                   │
  │                     ToolExecutor           │
  │                        │                   │
  │                        ▼                   │
  │                     ReportComposer         │
  │                        ├── 读取 active_template 的 parsed Markdown
  │                        ├── 注入章节结构约束
  │                        └── LLM 按模板生成报告
  │                                            │
  └── 修改报告 ──→ ModifyReportCommand         │
                    ├── 读取 current_report     │
                    ├── 读取 active_template    │
                    ├── 加载 report_modifier.md │
                    └── LLM 理解指令 → 重写报告
```

---

## 5. 代码改造清单

### 5.1 删除模块

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/domain/weight_engine.py` | **删除** | 纯 Skill 驱动，不再代码计算加权结果 |
| `src/domain/weight_engine.py` 引用 | 清理 | 删除所有 import WeightEngine 的代码 |

### 5.2 修改模块

| 文件 | 修改内容 |
|------|---------|
| `src/infrastructure/fault_parser.py` | 正则增加毫秒捕获；解析逻辑增加微秒处理 |
| `src/domain/report_composer.py` | 移除 `_extract_summary` 中的加权计算；改为读取模板 Markdown 注入 prompt；移除硬编码 `DEFAULT_CHAPTERS` |
| `src/domain/prompt_builder.py` | 增加模板注入；移除硬编码 JSON 输出格式说明 |
| `src/domain/skill_loader.py` | 解析 YAML frontmatter；支持按 description 匹配用户意图；提取 references 引用 |
| `src/application/commands/diagnose.py` | 移除 WeightEngine 调用；依赖 LLM 通过 Skill 自主计算 |
| `src/application/commands/modify_report.py` | 重写：读取模板约束 + LLM 理解自然语言指令 |
| `src/core/models.py` | `DiagnosisSession` 增加 `active_template_name`、`available_templates`；时间序列化配置 |
| `src/interfaces/web.py` | 新增模板相关 API：upload / list / activate / delete |
| `web/src/components/SessionSidebar.vue` | 时间显示改用固定格式函数（含毫秒） |
| `web/src/api/http.ts` | 新增模板相关 HTTP 接口 |
| `web/src/stores/sessionStore.ts` | 增加模板状态管理 |

### 5.3 新增模块

| 文件 | 职责 |
|------|------|
| `src/infrastructure/template_parser.py` | 模板解析器基类 + Markdown/Docx/Pdf 实现 |
| `src/domain/template_registry.py` | 模板注册表：列表、激活、缓存 |
| `src/application/commands/activate_template.py` | 激活模板 Command（只能激活一个） |
| `src/application/commands/upload_template.py` | 上传模板 Command |
| `src/application/commands/save_skill.py` | **重写**：LLM 生成符合 Agent Skill 规范的 Markdown |
| `src/application/commands/complete_diagnosis.py` | 修改：完成后提示保存技能 |
| `skills/comprehensive_diagnosis.md` | 重写：YAML frontmatter + 完整规则 |
| `skills/report_template_parser.md` | 模板解析 Skill |
| `skills/report_modifier.md` | 报告修改 Skill |
| `skills/references/diagnosis_rules.md` | 通用诊断规则 |
| `skills/references/report_structure.md` | 通用报告结构 |
| `skills/references/tool_guidelines.md` | 工具调用规范 |
| `templates/default.md` | 默认报告模板 |

### 5.4 依赖变更

新增 Python 包：
```
python-docx>=1.1.0      # Word 解析
pdfplumber>=0.11.0      # PDF 解析
PyYAML>=6.0             # YAML frontmatter 解析（已有，确认版本）
```

---

## 6. 关键交互流程

### 6.1 诊断流程（模板驱动）

```
用户: "220kV京西线#15杆塔跳闸，2026-05-21 08:30:15.123"
    │
    ▼
IntentClassifier → diagnose 意图
    │
    ▼
SkillLoader.load("comprehensive_diagnosis")
    ├── 解析 YAML frontmatter
    ├── 提取 description（确认触发）
    └── 提取 weights 配置
    │
    ▼
PromptBuilder.build()
    ├── 注入 comprehensive_diagnosis.md 全文
    ├── 注入 references/*.md
    ├── 注入可用工具目录
    ├── 注入激活模板（templates/parsed/xxx.md）
    └── 注入用户输入
    │
    ▼
DiagnosisPlanner.plan() → LLM 输出诊断计划（含工具列表）
    │
    ▼
ToolExecutor.execute() → 并行调用工具
    │
    ▼
ReportComposer.compose()
    ├── 读取激活模板 Markdown
    ├── 构建 prompt：工具输出 + 模板约束
    └── LLM 生成报告（按模板结构）
    │
    ▼
返回完整报告给用户
```

### 6.2 报告修改流程

```
用户: "把结论写得更确定一些，删除关于鸟害的描述"
    │
    ▼
IntentClassifier → modify_report 意图
    │
    ▼
ModifyReportCommand.execute()
    ├── 读取 current_report
    ├── 读取 active_template（约束）
    ├── 加载 report_modifier.md（指导 LLM 如何修改）
    ├── 构建 prompt：报告 + 指令 + 模板 + 修改规则
    └── LLM 生成修改后完整报告
    │
    ▼
保存新报告 → 记录 action_log → 返回给用户
```

### 6.3 模板上传流程

```
用户上传 "国网标准模板.docx"
    │
    ▼
POST /templates/upload
    │
    ▼
TemplateUploadHandler
    ├── 保存到 templates/uploads/国网标准模板.docx
    └── 触发 TemplateParser
    │
    ▼
DocxParser.parse()
    ├── python-docx 读取段落
    ├── 识别 Heading 1/2/3
    └── 提取标题后段落作为说明
    │
    ▼
生成 templates/parsed/国网标准模板.md
    │
    ▼
返回：上传成功，已解析为 Markdown
```

---

## 7. 附录：Skill 文件完整示例

### A.1 `comprehensive_diagnosis.md`

```markdown
---
name: comprehensive_diagnosis
description: |
  输电线路跳闸故障综合诊断专家。当用户描述输电线路故障、跳闸、
  线路异常、杆塔问题、雷击、覆冰、风偏、鸟害等情况时，必须使用此技能。
  即使用户没有明确说"诊断"，只要涉及线路名称+故障/异常/跳闸/闪络/
  接地/短路等关键词，都应自动触发此技能。
  适用于 220kV/500kV/750kV/1000kV 等各电压等级输电线路。
---

# 输电线路综合诊断

## 核心算法：加权置信度

所有工具返回的结果都有置信度（confidence，0~1 之间）。
你必须按以下公式计算每个工具的加权置信度：

```
加权置信度 = 工具返回的 confidence × 该工具的 weight
```

最终按加权置信度从高到低排序，最高者对应的故障类型为主要原因。
如果两个工具加权置信度差距 < 0.1，则列为并列主要原因。

## 工具权重配置

```yaml
weights:
  LightningDiagnosisTool: 1.0
  IcingDiagnosisTool: 0.9
  WindDiagnosisTool: 0.8
  BirdDamageDiagnosisTool: 0.6
```

## 工具调用策略

| 工具 | 权重 | 调用条件 |
|------|------|---------|
| LightningDiagnosisTool | 1.0 | 始终调用 |
| IcingDiagnosisTool | 0.9 | 气温 ≤ 5°C 或冬季时调用，否则主动跳过 |
| WindDiagnosisTool | 0.8 | 始终调用 |
| BirdDamageDiagnosisTool | 0.6 | 始终调用 |

## 诊断流程

1. **信息提取**：从用户描述中提取线路名称、杆塔号、故障时间（精确到毫秒）
2. **天气判断**：获取当前季节和天气，判断覆冰工具是否适用
3. **并行诊断**：同时调用所有符合条件的工具
4. **加权计算**：对每个工具结果计算 加权置信度 = confidence × weight
5. **排序判断**：按加权置信度降序排列，最高者为主要原因
6. **报告生成**：按激活模板的章节结构组织输出

## 置信度等级划分

- HIGH（高置信度）：加权置信度 ≥ 0.7
- MEDIUM（中置信度）：加权置信度 0.4 ~ 0.7
- LOW（低置信度）：加权置信度 < 0.4

## 注意事项

- 覆冰诊断仅在低温条件下有意义，夏季应主动跳过
- 如多个工具指向同一故障类型，应合并证据提升置信度
- 新增工具可用时，应提示用户是否纳入本次诊断
- 故障时间必须精确到毫秒，格式为 YYYY-MM-DD HH:MM:SS.mmm
- 报告结论中必须明确列出每个工具的加权置信度计算过程
```

### A.2 解析后的模板示例

```markdown
# 国网标准模板

> 来源文件：国网标准模板.docx
> 解析时间：2026-05-21 10:30:05.013
> 原始格式：docx

## 报告标题

输电线路故障诊断报告

## 章节结构

### 第1章：概述
- **内容指导**：简要描述故障概况，包括线路名称、故障时间（精确到毫秒）、故障类型
- **原始位置**：第1页，Heading 1

### 第2章：故障分析
- **内容指导**：分析故障原因，结合气象数据和历史记录
- **原始位置**：第1页，Heading 2

### 第3章：诊断证据
- **内容指导**：按工具分类列出详细诊断结果，包含每个工具的原始置信度和加权置信度
- **原始位置**：第2页，Heading 2

### 第4章：诊断结论
- **内容指导**：明确判定主要原因和次要原因，必须列出加权置信度计算过程和排序
- **原始位置**：第2页，Heading 2

### 第5章：处理建议
- **内容指导**：给出具体的运维和检修建议
- **原始位置**：第3页，Heading 2
```

---

## 8. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 不遵循 Skill 中的加权规则 | 诊断结论错误 | Skill 中强调"必须"计算；report_structure 要求结论中列出计算过程；Grader 断言验证 |
| Word/PDF 解析不准确 | 模板章节缺失或错乱 | 解析后展示给用户确认；支持人工修正 parsed markdown |
| 报告修改导致内容丢失 | 用户数据损失 | 保留历史版本；action_log 记录修改前后摘要 |
| Skill 描述不够 pushy 导致不触发 | 功能不可用 | 按 skill-creator 方法论优化 description；20+ 条触发 eval 测试 |

---

*设计文档版本：v1.0*
*日期：2026-05-21*
*状态：待审核*
