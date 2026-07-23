# 天气诊断浏览器智能体设计文档

> **日期**: 2025-05-11
> **状态**: 已批准，待实现
> **方案**: AI 浏览器智能体（Playwright + LLM Vision）

---

## 1. 背景与目标

### 1.1 背景

现有诊断工具（雷电、覆冰、风偏、鸟害）均使用模拟数据。用户需要接入真实数据源，但部分数据源（如天气查询）需要通过浏览器访问，涉及页面交互、登录、甚至人机验证。

### 1.2 目标

实现一个**天气诊断工具**，能够：

1. 自动打开浏览器，访问百度
2. 搜索指定城市天气
3. 从搜索结果页提取当前天气状况
4. 返回结构化的天气数据

**demo 阶段查询条件固定为"武汉"**，参数提取功能预留扩展点。

---

## 2. 架构设计

### 2.1 新增组件

```
src/
├── infrastructure/
│   ├── adapters/
│   │   ├── browser_agent_adapter.py    # 浏览器智能体适配器
│   │   └── browser/
│   │       ├── controller.py           # Playwright 浏览器生命周期
│   │       ├── agent_loop.py           # LLM 决策主循环
│   │       └── action_executor.py      # 动作执行器
│   └── llm_service.py                  # 已有，复用
├── config/tools/
│   └── weather.yaml                    # 天气工具配置
```

### 2.2 与现有系统集成

- `BrowserAgentAdapter` 继承 `ToolAdapter`（已有接口）
- 通过 YAML 配置注册到 `ToolRegistry`，与其他工具并列
- 复用现有的 `LLMService`（已接入 gemma-4-31B-it）
- 输出统一为 `ToolOutput` 格式

### 2.3 数据流

```
用户输入："220kV武汉线跳闸"
    ↓
FaultContext(line_name="武汉线")
    ↓
BrowserAgentAdapter.execute()
    ├─→ 查询参数：{"city": "武汉"}（demo 阶段硬编码）
    ├─→ BrowserController 启动浏览器
    ├─→ AgentLoop 开始循环：
    │      截图 → LLM 分析 → 决定动作 → 执行 → ...
    └─→ 提取天气数据，封装为 ToolOutput
    ↓
返回：{temperature, humidity, condition, ...}
```

---

## 3. 核心组件设计

### 3.1 BrowserController

负责 Playwright 浏览器的生命周期管理。

```python
class BrowserController:
    async def launch(self) -> None:
        """启动 headless Chromium"""
        
    async def new_page(self) -> Page:
        """创建新页面"""
        
    async def screenshot(self) -> bytes:
        """截取当前页面全屏截图"""
        
    async def close(self) -> None:
        """关闭浏览器"""
```

### 3.2 AgentLoop

浏览器智能体的决策主循环。

```python
class AgentLoop:
    async def run(self, task: str, max_steps: int = 10) -> str:
        """
        执行浏览器任务。
        
        循环直到：
        - LLM 返回 action="finish"
        - 达到 max_steps 限制
        - 发生不可恢复错误
        """
```

**循环逻辑：**

1. 截取当前页面截图（base64）
2. 构建包含任务描述、历史动作、截图的 LLM prompt
3. 调用 LLM 获取下一步决策
4. 解析决策 JSON，执行对应动作
5. 记录动作历史
6. 重复

### 3.3 ActionExecutor

将 LLM 决策转换为 Playwright 实际操作。

**支持的动作类型：**

| 动作 | 参数 | 说明 |
|------|------|------|
| `navigate` | `value`: URL | 访问指定页面 |
| `click` | `target`: 元素描述 | 点击页面元素 |
| `type` | `target`, `value` | 在输入框填入内容 |
| `scroll` | `value`: "down"/"up" | 滚动页面 |
| `wait` | 无 | 等待页面加载 |
| `finish` | `answer`: 结果文本 | 任务完成 |

**元素定位策略（分层容错）：**

```
LLM 返回 target="搜索按钮"
    │
    ▼
第1层：语义匹配
    ├─ 获取页面可交互元素列表
    ├─ 为每个元素生成描述文本
    ├─ 用文本相似度匹配 target_description
    └─ 点击最匹配的元素 [data-agent-id="N"]
    │
    ▼ 未找到
第2层：视觉坐标（备用）
    ├─ 将截图 + target 传给 LLM
    └─ LLM 返回 x, y 坐标
    └─ Playwright 点击该坐标
    │
    ▼ 失败
抛出异常，AgentLoop 终止或重试
```

**可交互元素标记：**

执行前注入 JS，为 `button, input, a, select, textarea` 添加 `data-agent-id` 属性，便于 Playwright 精确定位。

---

## 4. LLM Prompt 设计

### 4.1 Agent 决策 Prompt

```
你是浏览器自动化助手。当前任务：{task}

[历史动作]
{action_history}

[当前页面截图]
<img src="data:image/png;base64,{screenshot}" />

请分析当前页面，决定下一步动作。

可交互元素列表：
{interactive_elements}

返回 JSON 格式：
{
  "thought": "对当前页面的分析...",
  "action": "click|type|scroll|wait|navigate|finish",
  "target": "元素描述或null",
  "value": "输入值或URL或null",
  "answer": "任务完成时的答案或null"
}
```

### 4.2 Prompt 约束

- `action` 必须是允许值之一，否则视为无效
- `target` 使用自然语言描述，由 ActionExecutor 解析为具体元素
- `answer` 仅在 `action="finish"` 时有效

---

## 5. 天气诊断具体流程

### 5.1 查询流程示例

| 步骤 | 动作 | 参数 | 页面状态 |
|------|------|------|---------|
| 1 | navigate | https://www.baidu.com | 百度首页 |
| 2 | type | target="搜索框", value="武汉天气" | 输入完成 |
| 3 | click | target="百度一下按钮" | 搜索结果页加载中 |
| 4 | wait | | 天气结果展示 |
| 5 | finish | answer="武汉今日晴，25°C..." | 任务完成 |

### 5.2 输出格式

```python
ToolOutput(
    tool_name="WeatherDiagnosisTool",
    raw_text="武汉今日晴，25°C，湿度60%，东风2级",
    structured_data={
        "city": "武汉",
        "temperature": 25,
        "humidity": 60,
        "condition": "晴",
        "wind_direction": "东",
        "wind_level": "2级",
    },
    metadata={"source": "baidu", "query_time": "2025-05-11T10:00:00"},
)
```

---

## 6. 错误处理

| 异常场景 | 处理策略 |
|---------|---------|
| 浏览器启动失败 | 重试 1 次，仍失败返回错误 ToolOutput |
| 页面加载超时 | 截图 → LLM 判断是否继续等待或终止 |
| 元素找不到 | 先 wait 2 秒重试，再失败则终止 |
| LLM 返回无效 JSON | 重试最多 2 次，仍无效则终止 |
| 达到最大步数 | 返回已收集信息 + 未完成标记 |
| 人机验证（CAPTCHA） | LLM 尝试解答；无法通过则提示需人工干预 |

### 6.1 安全机制

- **沙箱隔离**：Playwright 使用独立浏览器上下文
- **超时控制**：单步 30 秒，整体任务 5 分钟
- **域名白名单**：可配置允许访问的域名列表

---

## 7. 配置

### 7.1 工具配置（weather.yaml）

```yaml
tool:
  name: "WeatherDiagnosisTool"
  display_name: "天气诊断"
  description: "通过浏览器访问百度查询指定城市天气状况"
  category: "environmental"
  adapter:
    type: "custom"
    config:
      module: "src.infrastructure.adapters.browser_agent_adapter"
      class: "BrowserAgentAdapter"
      # demo 阶段固定查询城市
      default_city: "武汉"
      # 浏览器配置
      headless: true
      max_steps: 10
      step_timeout: 30
  output_schema:
    type: "structured"
    fields:
      - name: "temperature"
        type: "float"
        description: "温度(°C)"
      - name: "humidity"
        type: "float"
        description: "湿度(%)"
      - name: "condition"
        type: "string"
        description: "天气状况"
      - name: "wind_direction"
        type: "string"
        description: "风向"
      - name: "wind_level"
        type: "string"
        description: "风力等级"
  report_mapping:
    chapter: "诊断证据"
    render_template: "table"
```

---

## 8. 测试策略

### 8.1 单元测试

- Mock LLM 返回固定决策序列
- 验证 ActionExecutor 正确解析决策并调用 Playwright API
- 验证 AgentLoop 在 max_steps 时终止

### 8.2 集成测试

- 使用 headless Playwright 访问本地测试 HTML 页面
- 验证完整查询流程：导航 → 输入 → 点击 → 提取

### 8.3 视觉回归

- 对关键步骤截图保存
- 比对预期结果（用于调试 LLM 决策质量）

---

## 9. 未来扩展

| 功能 | 说明 |
|------|------|
| 参数提取 | 从 `line_name` 或用户消息中提取城市名、日期等查询参数 |
| 多数据源 | 支持中国天气网、和风天气等除百度外的数据源 |
| 登录支持 | 处理需要登录的查询系统 |
| CAPTCHA 解决 | 集成外部验证码服务或更强的 LLM 视觉模型 |
| 缓存机制 | 短时间内重复查询同一城市，直接返回缓存结果 |

---

## 10. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 百度页面改版 | 高 | LLM 基于语义理解，不依赖固定选择器；定期回归测试 |
| LLM 决策错误 | 中 | 分层定位容错；max_steps 限制；截图留痕便于调试 |
| 浏览器资源占用 | 中 | 任务完成后立即关闭浏览器；限制并发数 |
| 网络波动 | 低 | 单步超时重试；整体超时保护 |

---

*文档结束*
