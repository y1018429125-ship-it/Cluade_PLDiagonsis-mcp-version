# 输电线路故障诊断智能体 - 产品技术文档

> **版本**: v0.1.2  
> **日期**: 2025-05-07  
> **状态**: 开发中（模拟数据阶段）
>
> **更新记录**:
> - v0.1.2 (2025-05-07): 修复重新诊断数据丢失问题、统一模块导入路径、修复权重传递一致性
> - v0.1.1 (2025-05-07): 修复会话内修改理解问题、恢复数据后创建未命名会话问题
> - v0.1.0 (2025-04-23): 初始版本

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心功能模块](#2-核心功能模块)
3. [会话管理规则](#3-会话管理规则)
4. [交互设计与用户体验](#4-交互设计与用户体验)
5. [技术架构](#5-技术架构)
6. [数据模型](#6-数据模型)
7. [API接口](#7-api接口)
8. [前端实现](#8-前端实现)
9. [预留功能与后续规划](#9-预留功能与后续规划)
10. [已知问题与修复计划](#10-已知问题与修复计划)

---

## 1. 项目概述

### 1.1 项目背景

构建一个专业领域AI智能体，用于输电线路故障（雷电、覆冰、风偏、鸟害等）的自动化诊断研判，支持：
- 诊断能力的动态扩展（MCP工具 + Markdown Skill）
- 专家经验的闭环学习（Human-in-the-Loop）
- 规范化报告的生成（模板驱动 + 分段填充）

### 1.2 核心特性

| 特性 | 说明 |
|------|------|
| **能力调度体系** | MCP原子化工具 + 动态Skill加载 |
| **闭环进化机制** | 实时干预 + 经验固化 |
| **触发机制** | 统一入口，支持手动/自动触发 |
| **规范化报告** | 模板驱动 + 分段填充 |
| **会话管理** | 多线路并行诊断 + 版本追踪 |

### 1.3 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.8+, Flask |
| 数据验证 | Pydantic |
| 模板引擎 | Jinja2 |
| 前端 | 原生HTML/CSS/JS + SSE |
| LLM接口 | OpenAI API / Mock |
| 配置管理 | YAML |

---

## 2. 核心功能模块

### 2.1 功能架构图

```
┌─────────────────────────────────────────────────────────┐
│                      用户交互层                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 对话诊断  │  │ 报告模板  │  │ 诊断报告  │  │ 系统设置  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────┐
│                      意图识别层                           │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│  │ 故障诊断 │ │ 排除工具 │ │ 重新检查 │ │ 权重调整 │ │ 会话管理 │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────┐
│                      诊断引擎层                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │ 触发解析   │  │ MCP工具调用│  │ 加权分析   │  │ 报告生成   ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
└─────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────┐
│                      数据服务层                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 会话管理   │  │ Skill管理  │  │ 模板管理   │  │ 报告存储   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 功能模块详解

#### 2.2.1 故障诊断

**流程**:
1. 用户输入故障描述
2. 触发器解析线路信息、故障类型、时间
3. 创建/复用诊断会话
4. 并行调用所有MCP诊断工具
5. 加权分析确定主要诊断
6. 生成诊断报告
7. 保存到会话历史

**支持的故障类型**:
- 雷电（LightningDiagnosisTool）
- 覆冰（IcingDiagnosisTool）
- 风偏（WindDiagnosisTool）
- 鸟害（BirdDamageDiagnosisTool）

#### 2.2.2 排除诊断

**场景**: 用户认为某类诊断不正确，要求排除后重新分析

**实现**:
- 将指定工具加入排除列表
- 从当前结果中过滤被排除的数据
- **不重新调用MCP**（节省资源）
- 使用现有数据重新加权分析
- 生成新版本诊断报告

#### 2.2.3 重新检查

**场景**: 用户要求重新获取某类诊断的最新数据

**实现**:
- 从排除列表恢复（如果有）
- 重新调用指定MCP工具
- 更新诊断结果
- 重新加权分析
- 生成新版本诊断报告

#### 2.2.4 权重调整

**支持方式**:
- 绝对调整: "提高雷电权重到1.2"
- 相对调整: "调高鸟害权重"（默认±0.3）

**权重范围**: 0.1 - 2.0

**默认权重**:
| 故障类型 | 权重 |
|---------|------|
| 雷电 | 1.0 |
| 覆冰 | 0.9 |
| 风偏 | 0.8 |
| 鸟害 | 0.6 |

#### 2.2.5 自定义Skill

**用途**: 保存用户的诊断偏好配置，方便复用

**保存内容**:
- 排除的工具列表
- 权重配置
- 触发条件

**使用方式**:
- "保存策略 [名称]" - 保存当前配置为策略
- "使用 [策略名]" - 激活已保存策略
- "/skills" - 查看所有策略

#### 2.2.6 报告修改（新增 v0.1.1）

**场景**: 用户在诊断会话中要求修改生成的诊断报告

**触发条件**:
- 当前会话状态为 `modifying` / `completed` / `excluded` / `rechecking`
- 用户输入包含修改关键词（去掉、删除、移除、增加、添加、插入、修改、调整、更新）
- 用户输入包含报告相关关键词（章、节、段、部分、内容、报告、结论、建议、分析、概述）

**实现**:
1. 使用LLM理解用户的修改意图
2. 解析修改操作（remove/add/modify）和目标（章节名）
3. 对当前报告执行修改
4. 保存修改后的报告为新版本
5. 保持会话状态为 `MODIFYING`

**支持的修改操作**:
| 操作 | 示例 | 说明 |
|------|------|------|
| 删除章节 | "去掉第六章" | 删除指定章节 |
| 删除章节 | "删除诊断结论" | 删除指定章节 |
| 添加内容 | "添加新的建议" | 在报告末尾添加 |
| 修改内容 | "修改概述部分" | 附加修改说明 |

**章节识别映射**:
| 用户表述 | 实际章节 |
|---------|---------|
| 第一章 / 第一节 / 概述 | 概述 |
| 第二章 / 第二节 / 故障分析 | 故障分析 |
| 第三章 / 第三节 / 诊断证据 | 诊断证据 |
| 第四章 / 第四节 / 诊断结论 | 诊断结论 |
| 第五章 / 第五节 / 处理建议 | 处理建议 |
| 第六章 / 第六节 / 附录 / JSON | 附录 |

---

## 3. 会话管理规则

### 3.1 会话生命周期

```
┌─────────┐    用户输入故障描述    ┌───────────┐
│  PENDING │ ───────────────────→ │ DIAGNOSING │
│ (排队中) │                      │ (诊断中)   │
└─────────┘                      └───────────┘
                                        │
                                        │ 诊断完成
                                        ▼
                              ┌───────────┐
                              │ MODIFYING │◄────────┐
                              │ (待确认)  │         │
                              └───────────┘         │
                                    │               │
                    ┌───────────────┼───────────────┘
                    │               │
                    ▼               │ 继续调整
            ┌───────────┐          │
            │ COMPLETED │          │
            │ (已完成)  │          │
            └───────────┘          │
                    │              │
                    │ 重新检查     │
                    ▼              │
            ┌───────────┐         │
            │ RECHECKING│─────────┘
            │ (重新检查)│
            └───────────┘
                    │
                    │ 排除工具
                    ▼
            ┌───────────┐
            │ EXCLUDED  │
            │ (已排除)  │
            └───────────┘
```

### 3.2 会话创建规则

#### 3.2.1 当前实现（模拟程序阶段）

| 场景 | 行为 |
|------|------|
| 首次诊断某线路 | 创建新会话 |
| 同一线路再次诊断 | **复用现有会话**（按核心线路名去重） |
| 当前会话中修改报告 | **保持当前会话**，直接执行 |
| 当前会话中调整/恢复数据 | **保持当前会话**，继续当前任务 |
| **全新线路名** | **新建会话** |

#### 3.2.2 关键规则（已修复 v0.1.1）

**规则1: 会话内上下文优先** ✅
- 在诊断会话中，用户说的"第六章"、"去掉雷电"等表述，默认指代**当前诊断报告**
- 大模型应理解这是同一会话内的上下文操作，直接规划并执行
- 不需要重新解释角色定位，也不需要用户再次确认

**实现**:
- `_detect_intent` 方法新增 `session_status` 和 `has_active_session` 参数
- 当会话状态为 `modifying/completed/excluded/rechecking` 时，优先判断为会话内操作
- 修改关键词 + 报告关键词 → `modify_report`
- 修改关键词 + 故障类型 → `exclude_tool` / `recheck_tool`

**规则2: 当前会话锁定** ✅
- 左侧诊断列表中，当前激活的会话只有一个
- 只要当前诊断任务没有明确结束（用户未主动切换或确认完成），所有输入归属**当前会话**
- 不需要用户手动去点左侧列表切换

**实现**:
- `_handle_recheck_tool_stream` 保存并恢复 `active_session_id`
- 重新检查后状态设为 `MODIFYING`（而非 `COMPLETED`）
- `_handle_diagnosis_stream` 移除 `status == COMPLETED` 时创建新会话的逻辑

**规则3: 线路名标准化**
- 使用 `LineNameNormalizer` 提取核心线路名
- 去掉电压等级、地区前缀等修饰
- 例如: "220kV京西线" → "京西线"

### 3.3 会话切换规则（预留）

#### 3.3.1 当前实现

| 维度 | 新会话触发条件 |
|------|---------------|
| **线路名** | 不同线路名称（标准化后） |

#### 3.3.2 后期预留（精细化实现）

| 维度 | 新会话触发条件 | 预留字段 |
|------|---------------|---------|
| **线路名** | 不同线路名称 | `line_name` |
| **时间** | 同线路，不同跳闸时间 | `fault_time` |
| **空间/区段** | 同线路，不同故障区段 | `fault_section` |

#### 3.3.3 预留数据模型

```python
会话标识 = {
    line_name: "220kV武昌线",        # 线路名
    fault_time: "2024-01-15 14:32",  # 跳闸时间（预留）
    fault_section: "K15+200~K18+500"  # 故障区段（预留）
}
```

> 当前阶段 `fault_time` 和 `fault_section` 可先留空或默认，只以 `line_name` 作为会话区分依据。后期接入真实调度数据后，再启用时间和区段维度。

---

## 4. 交互设计与用户体验

### 4.1 界面布局

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ 故障诊断智能体                                            │
├──────────┬─────────────────────────────┬──────────────────┤
│          │                             │                  │
│  💬 对话  │      主聊天区域            │   📋 诊断队列    │
│  📄 模板  │                             │   📚 诊断策略    │
│  📊 报告  │   [系统消息]               │                  │
│  ⚙️ 设置  │   [用户消息]               │   220kV京西线    │
│          │   [AI回复]                 │   110kV宁东线    │
│          │                             │                  │
│          │   [输入框]  [发送按钮]      │                  │
│          │                             │                  │
├──────────┴─────────────────────────────┴──────────────────┤
│  Enter发送 | Shift+Enter换行 | Ctrl+1/2/3 切换视图       │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 用户指令体系

#### 4.2.1 诊断相关

| 指令 | 功能 |
|------|------|
| "220kV京西线跳闸，雷击计数器动作" | 开始故障诊断 |
| "去掉雷电数据重新诊断" | 排除雷电诊断 |
| "重新检查雷电数据" | 重新获取雷电数据 |
| "提高雷电权重到1.2" | 绝对调整权重 |
| "调高鸟害权重" | 相对调整权重（+0.3） |
| **"去掉第六章"** | **删除报告章节（会话内）** |
| **"删除诊断结论"** | **删除报告章节（会话内）** |
| **"添加新的建议"** | **在报告末尾添加内容** |

#### 4.2.2 会话管理

| 指令 | 功能 |
|------|------|
| "会话列表" / "任务列表" | 查看所有诊断任务 |
| "切换到 session_XXX" | 切换到指定会话 |
| "确认完成" | 结束当前诊断 |

#### 4.2.3 策略管理

| 指令 | 功能 |
|------|------|
| "保存策略 [名称]" | 保存当前配置为策略 |
| "使用 [策略名]" | 激活指定策略 |
| "/skills" | 查看所有策略 |

### 4.3 流式输出设计

前端使用 **Server-Sent Events (SSE)** 实现流式输出：

```
event: start    → 开始处理
event: thinking → 分析用户意图...
event: thinking → 解析故障信息...
event: thinking → 执行综合故障诊断...
event: result   → 诊断结果片段
event: thinking → 生成诊断报告...
event: complete → 完整回复 + 报告路径
event: error    → 错误信息
```

### 4.4 状态可视化

| 状态 | 图标 | 颜色 |
|------|------|------|
| pending | ⏸️ | 黄色 |
| diagnosing | 🔄 | 蓝色 |
| completed | ✅ | 绿色 |
| reviewing | 📝 | 橙色 |
| modifying | 🔧 | 紫色 |
| excluded | 🚫 | 红色 |
| rechecking | 🔍 | 灰色 |

---

## 5. 技术架构

### 5.1 项目结构

```
PLdiagnosis/
├── src/
│   ├── core/              # 核心框架
│   │   ├── config_manager.py   # 配置管理
│   │   ├── llm_service.py      # LLM服务封装
│   │   ├── mcp_registry.py     # MCP工具注册表
│   │   ├── models.py           # 数据模型定义
│   │   └── __init__.py
│   ├── mcp_tools/         # MCP工具实现
│   │   ├── diagnosis_tools.py  # 诊断工具（雷电/覆冰/风偏/鸟害）
│   │   └── __init__.py
│   ├── diagnosis/         # 诊断引擎
│   │   ├── engine.py           # 诊断流程编排
│   │   └── __init__.py
│   ├── report/            # 报告生成
│   │   ├── generator.py        # 模板驱动报告生成
│   │   └── __init__.py
│   ├── trigger/           # 触发机制
│   │   ├── handler.py          # 触发处理器（手动/提问/SCADA）
│   │   └── __init__.py
│   ├── skills/            # Skill加载与管理
│   │   ├── loader.py           # Markdown Skill解析
│   │   └── __init__.py
│   ├── override/          # 覆盖层机制
│   │   ├── hitl.py             # Human-in-the-Loop
│   │   └── __init__.py
│   └── utils/             # 工具函数
│       └── line_name.py        # 线路名称标准化
├── skills/                # Markdown技能文件
├── templates/             # 报告模板（Jinja2）
├── tests/                 # 测试用例
├── docs/                  # 文档
├── config/                # 配置文件
├── examples/              # 示例数据
├── web/                   # Web前端
│   ├── index.html         # 主页面
│   └── static/
│       ├── css/style.css   # 样式
│       └── js/app.js       # 前端逻辑
├── main.py                # CLI入口
├── web_app.py             # Web服务入口（Flask）
├── requirements.txt       # 依赖
└── pyproject.toml         # 项目配置
```

### 5.2 核心组件关系

```
┌─────────────────────────────────────────────────────────┐
│  WebAgent (web_app.py)                                   │
│  ├── sessions: Dict[str, DiagnosisSession]              │
│  ├── active_session_id: str                              │
│  ├── diagnosis_engine: DiagnosisEngine                  │
│  ├── report_generator: ReportGenerator                  │
│  ├── skill_manager: SkillManager                        │
│  └── trigger_router: TriggerRouter                      │
│  └── _detect_intent() - 意图识别（支持会话上下文）       │
│  └── _handle_modify_report_stream() - 报告修改 (v0.1.1)  │
│  └── _handle_exclude_tool_stream() - 排除诊断            │
│  └── _handle_recheck_tool_stream() - 重新检查            │
│  └── _parse_modify_request() - 解析修改请求 (v0.1.1)     │
│  └── _apply_report_modification() - 应用修改 (v0.1.1)    │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ TriggerRouter │  │DiagnosisEngine│  │ReportGenerator│
│  - 解析输入   │  │  - 调用MCP    │  │  - 模板渲染   │
│  - 提取线路   │  │  - 加权分析   │  │  - LLM增强   │
│  - 识别意图   │  │  - 确定主诊断 │  │  - 分段生成   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                  │                  │
        ▼                  ▼                  │
┌──────────────┐  ┌──────────────┐           │
│ MCP Registry  │  │ SkillManager  │           │
│  - 工具注册   │  │  - 加载Skill  │           │
│  - 并行执行   │  │  - 激活策略   │           │
│  - 结果收集   │  │  - 保存配置   │           │
└──────────────┘  └──────────────┘           │
        │                                     │
        ▼                                     ▼
┌─────────────────────────────────────────────────────────┐
│  MCP Tools (模拟数据)                                     │
│  ├── LightningDiagnosisTool (雷电定位系统)                │
│  ├── IcingDiagnosisTool (气象预警系统)                   │
│  ├── WindDiagnosisTool (气象服务)                        │
│  └── BirdDamageDiagnosisTool (鸟害监测)                  │
└─────────────────────────────────────────────────────────┘
```

### 5.3 数据流

```
用户输入
    │
    ▼
┌─────────────────┐
│  意图识别        │
│  _detect_intent  │
│  (支持会话上下文) │
└─────────────────┘
    │
    ├─→ "diagnosis" → 创建/复用会话 → 调用诊断引擎 → 生成报告
    ├─→ "modify_report" → 获取当前会话 → 修改报告 → 保存新版本 (v0.1.1)
    ├─→ "exclude_tool" → 获取当前会话 → 排除工具 → 重新加权 → 生成报告
    ├─→ "recheck_tool" → 获取当前会话 → 重新调用MCP → 重新加权 → 生成报告
    ├─→ "weight_adjust" → 调整权重 → 返回确认
    ├─→ "list_sessions" → 返回会话列表
    ├─→ "switch_session" → 切换激活会话
    └─→ "general" → LLM通用回复
```

---

## 6. 数据模型

### 6.1 核心模型

#### 6.1.1 FaultContext - 故障上下文

```python
class FaultContext(BaseModel):
    line_id: str              # 线路ID
    line_name: str            # 线路名称
    tower_id: Optional[str]   # 杆塔ID
    fault_time: Optional[datetime]  # 故障时间（预留）
    weather_info: Optional[Dict]    # 天气信息
    scada_data: Optional[Dict]    # SCADA数据（预留）
    wave_data: Optional[Dict]       # 行波数据（预留）
    images: Optional[List[str]]     # 图像路径（预留）
    additional_info: Dict           # 附加信息
```

#### 6.1.2 DiagnosisResult - 诊断结果

```python
class DiagnosisResult(BaseModel):
    fault_type: FaultType     # 故障类型（雷电/覆冰/风偏/鸟害/...）
    confidence: float         # 置信度 (0.0-1.0)
    confidence_level: ConfidenceLevel  # 高/中/低
    evidence: List[str]       # 支撑证据
    details: Dict[str, Any]   # 详细诊断信息
    tool_name: str            # 诊断工具名称
    timestamp: datetime       # 诊断时间
```

#### 6.1.3 DiagnosisSummary - 诊断摘要

```python
class DiagnosisSummary(BaseModel):
    fault_context: FaultContext           # 故障上下文
    results: List[DiagnosisResult]        # 诊断结果列表
    primary_diagnosis: Optional[DiagnosisResult]  # 主要诊断
    all_evidence: List[str]               # 所有证据
    confidence_distribution: Dict[str, float]  # 置信度分布
    weights: Optional[Dict[str, float]]  # 诊断权重配置
    weighted_scores: Optional[Dict[str, Any]]  # 加权得分详情
    excluded_tools: List[str]             # 被排除的工具
    rechecked_tools: List[str]            # 重新检查过的工具
    version: int = 1                      # 诊断版本号
    parent_version: Optional[int]         # 父版本号
```

#### 6.1.4 DiagnosisSession - 诊断会话

```python
class DiagnosisSession(BaseModel):
    session_id: str                       # 会话ID
    line_name: str                        # 线路名称
    status: SessionStatus                 # 会话状态
    created_at: datetime                  # 创建时间
    updated_at: datetime                  # 更新时间
    summaries: List[DiagnosisSummary]     # 诊断历史版本
    current_summary: Optional[DiagnosisSummary]  # 当前诊断结果
    report_path: Optional[str]            # 报告路径
    user_actions: List[Dict[str, Any]]    # 用户操作历史
    active_weights: Dict[str, float]      # 当前权重
    excluded_tools: List[str]             # 已排除的工具
    custom_skill_name: Optional[str]      # 关联的自定义技能名
    rechecked_tools: List[str]            # 重新检查过的工具
```

### 6.2 会话状态机

```python
class SessionStatus(str, Enum):
    PENDING = "pending"           # 排队等待
    DIAGNOSING = "diagnosing"     # 正在诊断
    COMPLETED = "completed"       # 诊断完成
    REVIEWING = "reviewing"       # 报告审阅中
    MODIFYING = "modifying"       # 用户修改中（待确认）
    EXCLUDED = "excluded"         # 已排除某些工具
    RECHECKING = "rechecking"     # 正在重新检查
```

---

## 7. API接口

### 7.1 REST API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/chat` | 流式对话（SSE） |
| GET | `/api/sessions` | 获取会话列表 |
| GET | `/api/sessions/<id>` | 获取会话详情 |
| POST | `/api/sessions/<id>/switch` | 切换会话 |
| POST | `/api/sessions/clear` | 清空所有会话 |
| POST | `/api/templates/upload` | 上传模板 |
| GET | `/api/templates` | 获取模板列表 |
| GET | `/api/reports` | 获取报告列表 |
| GET | `/api/reports/<filename>` | 下载报告 |
| GET | `/api/settings` | 获取系统设置 |
| POST | `/api/settings/weights` | 更新权重配置 |
| GET | `/api/skills` | 获取技能列表 |
| POST | `/api/skills/<name>/activate` | 激活技能 |
| POST | `/api/skills/save` | 保存当前配置为技能 |
| DELETE | `/api/skills/<name>` | 删除自定义技能 |
| POST | `/api/skills/reset` | 恢复默认策略 |

### 7.2 SSE事件类型

| 事件 | 说明 |
|------|------|
| `start` | 开始处理 |
| `thinking` | 思考过程（可显示"正在分析..."） |
| `result` | 诊断结果片段 |
| `content` | 流式内容（逐字输出） |
| `complete` | 处理完成，包含完整数据 |
| `error` | 错误信息 |

---

## 8. 前端实现

### 8.1 技术栈

- **框架**: 原生JavaScript（无框架依赖）
- **样式**: 原生CSS
- **Markdown渲染**: marked.js
- **代码高亮**: highlight.js
- **实时通信**: Server-Sent Events (EventSource)

### 8.2 核心功能

| 功能 | 实现 |
|------|------|
| 会话队列 | 左侧边栏，每10秒自动刷新 |
| 流式输出 | SSE接收，实时追加到聊天区域 |
| Markdown渲染 | marked.js解析，支持表格/代码块/列表 |
| 模板管理 | 模态框上传/预览/切换 |
| 报告查看 | 模态框预览 + 下载 |
| 权重调整 | 滑块控件 + 实时显示 |

### 8.3 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| Enter | 发送消息 |
| Shift+Enter | 换行 |
| Ctrl+1 | 切换到对话视图 |
| Ctrl+2 | 切换到模板视图 |
| Ctrl+3 | 切换到报告视图 |

---

## 9. 预留功能与后续规划

### 9.1 短期（1-2个月）

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 会话持久化 | P0 | 重启后保留会话状态 |
| 历史对比 | P1 | 对比不同版本的诊断结果 |
| 批量操作 | P1 | 批量排除/重新检查多个工具 |
| 真实MCP接入 | P0 | 接入真实雷电定位/气象系统 |

### 9.2 中期（3-6个月）

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 时间和区段维度 | P1 | 同线路不同时间/区段创建新会话 |
| SCADA自动触发 | P1 | 接入调度系统，自动创建诊断会话 |
| 图像识别 | P2 | 支持上传故障现场照片分析 |
| 语音输入 | P2 | 支持语音描述故障 |

### 9.3 长期（6个月以上）

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 知识图谱 | P2 | 构建线路-故障-措施知识图谱 |
| 预测性维护 | P2 | 基于历史数据预测故障风险 |
| 多Agent协作 | P3 | 多个诊断Agent协同分析 |

### 9.4 会话管理精细化（预留）

```python
# 当前实现
会话标识 = {
    line_name: "220kV武昌线"
}

# 后期实现
会话标识 = {
    line_name: "220kV武昌线",
    fault_time: "2024-01-15 14:32:00",      # 新增
    fault_section: "K15+200~K18+500",         # 新增
    protection_action: "距离保护I段动作",      # 新增
    weather: "雷雨, 风速12m/s"                 # 新增
}
```

---

## 10. 已知问题与修复计划

### 10.1 已修复问题（v0.1.1）

| 问题 | 严重程度 | 描述 | 修复方案 | 状态 |
|------|---------|------|---------|------|
| 会话内修改理解错误 | **高** | 用户要求"去掉第六章"，系统返回角色定位说明而非直接执行 | 在诊断会话中，将报告修改指令理解为对当前报告的操作 | ✅ 已修复 |
| 恢复数据后创建未命名会话 | **高** | 去掉雷电后恢复，出现"未命名线路诊断报告" | 确保恢复操作在当前会话内执行，不创建新会话 | ✅ 已修复 |
| 重新诊断数据丢失 | **高** | 调整权重后重新诊断，报告数据为空（0条结果） | 统一模块导入路径，修复Pydantic类型验证失败 | ✅ 已修复 |
| 权重传递不一致 | **中** | 重新诊断时使用全局权重而非会话权重 | 使用 `session.active_weights` 替代 `self.active_weights` | ✅ 已修复 |

### 10.2 待修复问题

| 问题 | 严重程度 | 描述 | 修复方案 |
|------|---------|------|---------|
| 意图识别过于简单 | 中 | 基于关键词匹配，容易误判 | 引入LLM进行意图理解 |
| 报告章节操作不灵活 | 中 | 无法直接对报告章节进行增删改 | 增加报告结构化编辑能力 |
| 模块导入路径一致性 | 低 | 不同文件使用不同导入路径可能导致类型不匹配 | 统一使用 `src.` 前缀导入 |

### 10.3 修复方案详述（v0.1.2）

#### 问题3: 重新诊断数据丢失

**现象**: 用户调整权重后输入"重新诊断"，诊断报告结果为空（0条结果），主要诊断为"未知"。

**根因**: Python 模块双重导入导致 `FaultContext` 类型不匹配。

- `web_app.py` 使用 `from core.models import FaultContext` → 创建 `<class 'core.models.FaultContext'>`
- `mcp_registry.py` 使用 `from src.core.models import FaultContext` → 期望 `<class 'src.core.models.FaultContext'>`

虽然两个类内容完全相同，但 Python 认为它们是不同的类型，导致 Pydantic 验证失败：
```
Input should be a valid dictionary or instance of FaultContext
[type=model_type, input_value=FaultContext(...), input_type=FaultContext]
```

**修复方案**:
1. 统一 `web_app.py` 中所有导入路径，添加 `src.` 前缀
2. 确保所有模块使用一致的导入路径：`src.core.models` 而非 `core.models`

**关键代码变更**:
```python
# 修复前
from core.models import FaultContext, DiagnosisSession, SessionStatus
from core.mcp_registry import registry
from diagnosis.engine import DiagnosisEngine

# 修复后
from src.core.models import FaultContext, DiagnosisSession, SessionStatus
from src.core.mcp_registry import registry
from src.diagnosis.engine import DiagnosisEngine
```

#### 问题4: 权重传递不一致

**现象**: 重新诊断时，报告显示的权重与用户调整后的权重不一致。

**根因**: `_handle_diagnosis_stream` 中使用了 `self.active_weights`（全局权重），而非 `session.active_weights`（会话级别权重）。

**修复方案**:
1. 诊断执行时传入 `session_weights` 替代 `self.active_weights`
2. 权重信息显示使用 `session_weights`
3. 报告生成中的权重表格使用 `session_weights`

**关键代码变更**:
```python
# 修复前
diagnosis_result = await self.diagnosis_engine.diagnose(
    context, 
    skill_names=skill_names,
    weights=self.active_weights  # ❌ 使用全局权重
)

# 修复后
session_weights = active_session.active_weights
diagnosis_result = await self.diagnosis_engine.diagnose(
    context, 
    skill_names=skill_names,
    weights=session_weights  # ✅ 使用会话权重
)
```

**影响范围**:
- `_handle_diagnosis_stream` 方法中的权重传递
- 诊断结果事件中的 `weights` 字段
- 报告模板中的权重配置表格

---

### 10.4 修复方案详述（v0.1.1）

#### 问题1: 会话内修改理解错误

**根因**: `_detect_intent` 方法将"去掉第六章"识别为 `general` 意图，而非诊断会话内的报告修改。

**修复方案**:
1. 扩展 `_detect_intent` 方法 - 新增 `session_status` 和 `has_active_session` 参数
2. 增加会话内操作意图判断 - 当存在活跃会话且状态为 `modifying/completed/excluded/rechecking` 时：
   - 修改关键词 + 报告关键词 → `modify_report`
   - 修改关键词 + 故障类型 → `exclude_tool` / `recheck_tool`
3. 新增 `_handle_modify_report_stream` 方法 - 处理报告修改
4. 新增 `_parse_modify_request` 方法 - 规则解析修改请求
5. 新增 `_apply_report_modification` 方法 - 应用报告修改

**关键代码**:
```python
async def _detect_intent(self, message: str, session_status: str = None, has_active_session: bool = False) -> str:
    # 会话内操作意图（当存在活跃会话时优先判断）
    if has_active_session and session_status in ["modifying", "completed", "excluded", "rechecking"]:
        # 报告修改意图
        report_modify_keywords = ["去掉", "删除", "移除", "不要", "排除", "增加", "添加", "插入", "修改", "调整", "更新"]
        report_section_keywords = ["章", "节", "段", "部分", "内容", "报告", "结论", "建议", "分析", "概述"]
        if any(kw in message for kw in report_modify_keywords) and any(kw in message for kw in report_section_keywords):
            return "modify_report"
        
        # 在诊断会话中，"去掉/排除 + 故障类型" 应理解为排除诊断工具
        exclude_keywords = ["去掉", "排除", "删除", "移除", "不要"]
        tool_keywords = ["雷电", "覆冰", "风偏", "鸟害"]
        if any(kw in message for kw in exclude_keywords) and any(kw in message for kw in tool_keywords):
            return "exclude_tool"
        
        # 在诊断会话中，"重新检查/恢复 + 故障类型" 应理解为重新检查
        recheck_keywords = ["重新检查", "再次检查", "重新诊断", "再次诊断", "重新调用", "恢复"]
        if any(kw in message for kw in recheck_keywords) and any(kw in message for kw in tool_keywords):
            return "recheck_tool"
    
    # ... 原有意图识别逻辑
```

#### 问题2: 恢复数据后创建未命名会话

**根因**: `_handle_recheck_tool_stream` 中没有正确维护 `active_session_id`，导致后续输入被路由到新会话。

**修复方案**:
1. `_handle_recheck_tool_stream` 保存并恢复 `active_session_id`
2. 重新检查后状态设为 `MODIFYING`（而非 `COMPLETED`）
3. `_handle_diagnosis_stream` 移除 `status == COMPLETED` 时创建新会话的逻辑

**关键代码**:
```python
async def _handle_recheck_tool_stream(self, user_message: str):
    # 获取当前会话 - 强制使用当前活跃会话，不创建新会话
    session = self.get_active_session()
    if not session:
        yield error_event("没有活跃的诊断会话，请先进行诊断")
        return
    
    # 确保 active_session_id 不变，防止后续输入被路由到新会话
    original_session_id = self.active_session_id
    
    # ... 重新检查逻辑 ...
    
    # 重新检查后状态设为 MODIFYING
    session.status = SessionStatus.MODIFYING
    
    # 确保 active_session_id 保持不变
    self.active_session_id = original_session_id
```

```python
# _handle_diagnosis_stream 中移除以下逻辑:
# elif active_session.status == SessionStatus.COMPLETED:
#     should_create_new = True
```

---

## 附录

### A. 配置文件示例

```yaml
# config/config.yaml
llm:
  provider: openai
  model: gpt-4
  api_key: ${OPENAI_API_KEY}
  base_url: https://api.openai.com/v1

skills:
  directory: skills
  auto_load: true

report:
  templates_directory: templates
  default_template: default_report.md
```

### B. Skill文件示例

```markdown
# 排除雷电诊断策略

## Goal
在故障诊断中排除雷电因素，专注于其他故障类型分析

## Trigger Conditions
- 用户要求排除雷电进行诊断
- 故障诊断需要忽略雷电因素

## Tool Usage / Workflow
1. 解析故障上下文
2. 执行综合诊断，但排除 LightningDiagnosisTool
3. 使用当前权重配置进行加权分析
4. 生成诊断报告

## Constraints & Rules
- 禁止使用 LightningDiagnosisTool
- 遵循当前权重配置

## Output Format
标准诊断报告格式

## Metadata
- type: strategy
- priority: 8
```

### C. 报告模板示例

```markdown
# {{ title }}

> 生成时间: {{ generated_time }}

## 一、概述
{{ overview }}

## 二、故障分析
{{ fault_analysis }}

## 三、诊断证据
{{ evidence }}

## 四、诊断结论
{{ conclusion }}

## 五、处理建议
{{ recommendations }}
```

---

*文档结束 - 版本 v0.1.2 (2025-05-07)*
