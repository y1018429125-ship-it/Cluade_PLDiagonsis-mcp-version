# MCP 服务独立化与诊断流程优化设计

> 日期：2026-05-14
> 状态：待实现

## 背景

当前系统的 MCP 工具处于模拟数据模式，所有工具输出由 `MCPToolAdapter` 中的 mock 数据返回。本设计将 MCP 服务拆分为独立进程，同时将诊断权重从代码迁移到技能文件，并优化排除/恢复工具时的诊断流程。

## 目标

1. MCP 服务独立为 FastAPI 进程，主项目通过 HTTP 配置注册调用
2. 工具权重从代码硬编码迁移到 `comprehensive_diagnosis.md` 技能文件
3. 排除/恢复工具后重新诊断始终遵循当前激活技能
4. 排除工具时复用已有工具输出，避免重复 HTTP 请求

---

## 1. MCP 服务独立化

### 1.1 目录结构

```
PLDiagnosis/
├── src/                          # 主项目
│   └── ...
├── mcp-services/                 # 新增：独立 MCP 服务目录
│   ├── README.md
│   ├── pyproject.toml
│   ├── lightning-service/        # 雷电诊断服务
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── icing-service/            # 覆冰诊断服务
│   ├── wind-service/             # 风偏诊断服务
│   ├── bird-service/             # 鸟害诊断服务
│   └── weather-service/          # 天气查询服务
├── config/tools/
│   ├── lightning.yaml            # 增加 url 字段
│   ├── icing.yaml
│   ├── wind.yaml
│   ├── bird.yaml
│   └── weather.yaml
└── docker-compose.yml            # 增加 mcp-services 服务
```

### 1.2 MCP 服务接口

所有 MCP 服务统一暴露两个端点：

```http
GET /health
→ {"status": "ok", "tool_name": "LightningDiagnosisTool"}

POST /diagnose
→ 接收 JSON，返回工具诊断结果 JSON
```

示例请求：

```http
POST http://localhost:8001/diagnose
Content-Type: application/json

{
  "line_name": "武汉线",
  "voltage_level": "220kV",
  "fault_time": "2026-05-12T12:00:00",
  "additional_info": {}
}
```

示例响应：

```json
{
  "tool_name": "LightningDiagnosisTool",
  "raw_text": "雷电监测数据分析...",
  "structured_data": {
    "fault_type": "雷击跳闸",
    "confidence": 0.85,
    "evidence": ["雷电活动记录", "绝缘子闪络痕迹"],
    "details": "..."
  },
  "metadata": {"source": "雷电定位系统"},
  "timestamp": "2026-05-14T10:30:00"
}
```

### 1.3 MCP 服务模型（各服务独立定义）

每个 MCP 服务自行定义 Pydantic 模型，不共享：

```python
# mcp-services/lightning-service/models.py
from pydantic import BaseModel
from datetime import datetime
from typing import Any, Optional

class DiagnoseRequest(BaseModel):
    line_name: str
    voltage_level: Optional[str] = None
    fault_time: Optional[datetime] = None
    additional_info: dict = {}

class DiagnoseResponse(BaseModel):
    tool_name: str
    raw_text: str
    structured_data: dict[str, Any]
    metadata: dict[str, Any] = {}
    timestamp: datetime
```

### 1.4 MCP 服务启动（FastAPI）

```python
# mcp-services/lightning-service/main.py
from fastapi import FastAPI
from .models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Lightning Diagnosis MCP Service")

@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "LightningDiagnosisTool"}

@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    # TODO: 接入真实雷电数据源
    return DiagnoseResponse(
        tool_name="LightningDiagnosisTool",
        raw_text=f"雷电监测：{req.line_name} 在故障时段有雷电活动...",
        structured_data={
            "fault_type": "雷击跳闸",
            "confidence": 0.85,
            "evidence": ["雷电活动记录"],
        },
        metadata={"source": "雷电定位系统", "data_quality": "real"},
        timestamp=datetime.now(),
    )
```

### 1.5 主项目配置改造

`config/tools/lightning.yaml`：

```yaml
name: LightningDiagnosisTool
display_name: 雷电诊断
description: 基于雷电定位系统的故障诊断
category: 电气
adapter:
  type: mcp
  url: http://localhost:8001          # MCP 服务地址
  timeout: 30
  health_endpoint: /health
```

### 1.6 主项目 MCPToolAdapter 改造

```python
# src/infrastructure/adapters/mcp_adapter.py
import httpx
from src.domain.adapters.base import ToolAdapter
from src.core.models import ToolOutput, DiagnosisContext

class MCPToolAdapter(ToolAdapter):
    def __init__(self, config: dict):
        self.name = config["name"]
        self.display_name = config.get("display_name", self.name)
        self.description = config.get("description", "")
        self.category = config.get("category", "")
        self.url = config["adapter"]["url"]
        self.timeout = config["adapter"].get("timeout", 30)
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def execute(self, context: DiagnosisContext) -> ToolOutput:
        response = await self._client.post(
            f"{self.url}/diagnose",
            json={
                "line_name": context.line_name,
                "voltage_level": getattr(context, "voltage_level", None),
                "fault_time": getattr(context, "fault_time", None),
                "additional_info": getattr(context, "additional_info", {}),
            }
        )
        response.raise_for_status()
        data = response.json()
        return ToolOutput(**data)
```

### 1.7 启动方式

开发环境：

```bash
# start.sh 改造
python mcp-services/lightning-service/main.py --port 8001 &
python mcp-services/icing-service/main.py --port 8002 &
python mcp-services/wind-service/main.py --port 8003 &
python mcp-services/bird-service/main.py --port 8004 &
python mcp-services/weather-service/main.py --port 8005 &

# 等待服务就绪
sleep 2

# 启动主项目
python web_app.py
```

Docker Compose：

```yaml
services:
  lightning-service:
    build: ./mcp-services/lightning-service
    ports: ["8001:8001"]
    environment:
      - PORT=8001

  icing-service:
    build: ./mcp-services/icing-service
    ports: ["8002:8002"]

  wind-service:
    build: ./mcp-services/wind-service
    ports: ["8003:8003"]

  bird-service:
    build: ./mcp-services/bird-service
    ports: ["8004:8004"]

  weather-service:
    build: ./mcp-services/weather-service
    ports: ["8005:8005"]

  web:
    build: .
    ports: ["5000:5000"]
    environment:
      - LIGHTNING_URL=http://lightning-service:8001
      - ICING_URL=http://icing-service:8002
      - WIND_URL=http://wind-service:8003
      - BIRD_URL=http://bird-service:8004
      - WEATHER_URL=http://weather-service:8005
```

### 1.8 移除 Mock 模式

- 删除 `MCPToolAdapter` 中的 mock 分支代码
- 删除 `config/tools/*.yaml` 中的 `mock_data` 字段
- `HTTPMCPClient` 类可删除，功能合并到 `MCPToolAdapter`

---

## 2. 权重放入技能文件

### 2.1 技能 Markdown 文件格式

`skills/comprehensive_diagnosis.md` 改造：

```markdown
# 输电线路综合诊断策略

## 策略概述
针对输电线路常见故障的综合诊断方法，适用于常规运行条件下的故障分析。

## 工具权重配置

```yaml
weights:
  LightningDiagnosisTool: 1.0
  IcingDiagnosisTool: 0.9
  WindDiagnosisTool: 0.8
  BirdDamageDiagnosisTool: 0.6
```

## 诊断优先级
1. 雷电故障（权重最高，优先排查）
2. 覆冰故障
3. 风偏故障
4. 鸟害故障

## 报告模板
默认采用五章节结构：概述、故障分析、诊断证据、诊断结论、处理建议。

## 使用说明
本策略适用于春夏季节的常规故障诊断，冬季严寒条件下建议切换至覆冰专项策略。
```

### 2.2 SkillLoader 增加权重解析

```python
# src/domain/skill_loader.py
import re
import yaml

class SkillLoader:
    def load(self, name: str) -> tuple[str, dict]:
        """返回 (markdown正文, 权重配置字典)"""
        content = self._read_file(f"{name}.md")
        weights = self._extract_weights(content)
        return content, weights

    def _extract_weights(self, content: str) -> dict[str, float]:
        """从 Markdown 中提取 YAML 代码块里的 weights"""
        pattern = r'```yaml\s*(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return {}
        try:
            config = yaml.safe_load(match.group(1))
            return config.get("weights", {})
        except yaml.YAMLError:
            return {}
```

### 2.3 会话初始化加载技能权重

```python
# src/domain/session_manager.py
class SessionManager:
    def create(self, line_name: str) -> DiagnosisSession:
        session = DiagnosisSession(...)
        session.active_skill_name = self._default_skill_name

        # 从技能文件加载权重
        _, weights = self._load_skill_weights(session.active_skill_name)
        if weights:
            session.active_weights = weights
        else:
            session.active_weights = DEFAULT_WEIGHTS.copy()

        self._sessions[session.session_id] = session
        self._active_session_id = session.session_id
        self._persist()
        return session

    def _load_skill_weights(self, skill_name: str) -> tuple[str, dict]:
        """加载技能内容和权重"""
        from src.domain.skill_loader import SkillLoader
        loader = SkillLoader()  # 或从依赖注入获取
        return loader.load(skill_name)
```

### 2.4 切换技能时同步更新权重

```python
# 激活技能时（web.py / strategy_manager）
session.active_skill_name = "winter_diagnosis"
_, weights = skill_loader.load("winter_diagnosis")
if weights:
    session.active_weights = weights
    session.excluded_tools.clear()  # 切换技能时重置排除列表
```

### 2.5 权重加载优先级

从高到低：

1. 用户手动调整（`AdjustWeightCommand`）→ 存入 `session.active_weights`
2. 当前激活技能定义的权重 → 从 Markdown 解析
3. 系统默认值 `DEFAULT_WEIGHTS` → 兜底

### 2.6 DEFAULT_WEIGHTS 改造

```python
# src/core/models.py
# 保留为最小兜底值，但不作为默认创建值
DEFAULT_WEIGHTS: dict[str, float] = {
    "LightningDiagnosisTool": 1.0,
    "IcingDiagnosisTool": 0.9,
    "WindDiagnosisTool": 0.8,
    "BirdDamageDiagnosisTool": 0.6,
}
```

---

## 3. 重新诊断遵循当前技能

### 3.1 当前状态确认

经代码审查，以下逻辑已满足需求：

- `DiagnoseCommand.execute()` 开头使用 `session.active_skill_name` 加载技能
- `StateMachine` 允许 `MODIFYING` 状态下执行 `diagnose`
- `web.py` 在排除/恢复后自动触发 `DiagnoseCommand`

### 3.2 需优化点

#### A. 自动链式诊断前重建 ExecutionContext

```python
# web.py:157-180 改造
if intent_type in (IntentType.EXCLUDE_TOOL, IntentType.INCLUDE_TOOL):
    yield _sse_event(Event.thinking(session.session_id, "自动重新诊断..."))

    # 重建 diagnose 上下文（确保使用当前会话状态）
    diagnose_intent = Intent(
        intent_type=IntentType.DIAGNOSE,
        confidence=1.0,
        parameters={},
    )
    ctx = ContextBuilder.build(session, message, intent=diagnose_intent)

    diagnose_cmd = DiagnoseCommand(...)
    async for event in diagnose_cmd.execute(ctx):
        yield _sse_event(event)
        if event.event_type in (EventType.COMPLETE, EventType.ERROR):
            _append_chat_message(session, "assistant",
                event.payload.get("message", ""),
                event.event_type.value)
```

#### B. 重新诊断时发送技能名称提示

```python
# diagnose.py:83-86
skill_name = session.active_skill_name or "comprehensive_diagnosis"
yield Event.thinking(session.session_id, f"加载技能: {skill_name}")
skill_md, _ = self.skill_loader.load(skill_name)
```

### 3.3 重新诊断完整流程

```
用户: "排除鸟害诊断"
    │
    ▼
ExcludeToolCommand
    ├── session.excluded_tools += ["BirdDamageDiagnosisTool"]
    └── 状态保持 MODIFYING
    │
    ▼
自动触发 DiagnoseCommand
    │
    ├── skill_name = session.active_skill_name
    ├── skill_loader.load(skill_name) -> 技能正文 + 权重
    ├── 使用技能的权重配置
    ├── prompt_builder.build() -> 提示词含 excluded_tools
    ├── diagnosis_planner.plan() -> 规划排除鸟害后的诊断方案
    ├── tool_executor.execute() -> 调用剩余工具
    ├── report_composer.compose() -> 生成新报告
    └── 状态 MODIFYING
```

---

## 4. 排除工具时复用已有数据

### 4.1 设计原则

- 缓存存储在内存中，**不持久化**
- 每次全新诊断（`PENDING` 状态）时清除缓存
- 排除/恢复工具时复用未变更工具的缓存
- 复查工具时清除该工具缓存

### 4.2 会话增加临时缓存字段

```python
# src/core/models.py
class DiagnosisSession:
    ...
    # 非持久化字段：工具输出缓存
    tool_outputs_cache: dict[str, Any] = field(default_factory=dict, repr=False)
```

**注意**：`tool_outputs_cache` 不在 `model_dump()` 中序列化，不写入 `sessions.json`。

### 4.3 DiagnoseCommand 缓存逻辑

```python
async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
    session = ctx.session

    # 全新诊断时清除缓存
    if session.status == SessionStatus.PENDING:
        session.tool_outputs_cache.clear()

    ...

    # 步骤 7 改造：执行工具（带缓存）
    yield Event.thinking(session.session_id, "执行诊断工具...")

    planned_tools = plan.get("tools_to_call", [])
    planned_names = {t["name"] for t in planned_tools}

    # 复用缓存
    cached_outputs = {}
    names_to_call = []

    for tool_name in planned_names:
        if tool_name in session.tool_outputs_cache:
            cached_outputs[tool_name] = session.tool_outputs_cache[tool_name]
            yield Event.thinking(session.session_id,
                f"复用 {tool_name} 历史数据...")
        else:
            names_to_call.append(tool_name)

    # 只调用未缓存的工具
    if names_to_call:
        partial_plan = {
            "tools_to_call": [t for t in planned_tools if t["name"] in names_to_call],
            "parallel": plan.get("parallel", True),
        }
        diagnosis_ctx = DiagnosisContext(
            session_id=session.session_id,
            line_name=session.line_name,
        )
        new_outputs = await self.tool_executor.execute(partial_plan, diagnosis_ctx)
    else:
        new_outputs = {}

    # 合并结果
    tool_outputs = {**cached_outputs, **new_outputs}

    # 新结果存入缓存
    for name, output in new_outputs.items():
        session.tool_outputs_cache[name] = output

    # 发送结果事件
    for name, output in tool_outputs.items():
        yield Event.result(session.session_id, {
            "tool": name,
            "output": output.model_dump(mode="json")
        })

    ...
```

### 4.4 RecheckToolCommand 清除缓存

```python
# src/application/commands/recheck.py
class RecheckToolCommand(Command):
    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        ...
        tool_name = ctx.intent.parameters.get("tool_name")

        # 清除该工具缓存，强制重新调用
        if tool_name in ctx.session.tool_outputs_cache:
            del ctx.session.tool_outputs_cache[tool_name]

        # 重新执行工具
        ...
```

### 4.5 缓存策略总结

| 场景 | 缓存行为 |
|------|---------|
| 首次诊断（PENDING -> DIAGNOSING） | 清除全部缓存，全部调用 |
| 排除工具后重新诊断 | 复用未排除工具的缓存，不调用被排除工具 |
| 恢复工具后重新诊断 | 复用已有缓存，调用刚恢复的工具 |
| 复查工具 | 清除该工具缓存，重新调用，其他工具复用缓存 |
| 切换技能 | 缓存保留（数据不变，只变权重） |
| 用户新输入（非排除/恢复） | 视为新诊断，清除缓存 |
| 完成诊断（COMPLETED） | 缓存保留（查看报告用） |

### 4.6 排除工具后重新诊断的数据流

```
用户: "排除鸟害诊断"
    │
    ▼
ExcludeToolCommand
    ├── session.excluded_tools = ["BirdDamageDiagnosisTool"]
    └── 状态 MODIFYING
    │
    ▼
自动 DiagnoseCommand
    │
    ├── plan.tools_to_call = [Lightning, Icing, Wind]
    ├── 缓存检查:
    │   ├── Lightning -> 命中 ✅ 复用
    │   ├── Icing -> 命中 ✅ 复用
    │   ├── Wind -> 命中 ✅ 复用
    │   └── Bird -> 不在 plan 中，跳过
    ├── 调用: 无（全部命中缓存）
    ├── WeightEngine 计算（不含 Bird）
    ├── ReportComposer 生成报告
    └── 状态 MODIFYING
    │
    ▼
返回 complete
    节省: 0 次 HTTP 请求（对比之前 3 次）
```

---

## 5. 数据模型变更

### 5.1 DiagnosisSession

```python
# src/core/models.py
@dataclass
class DiagnosisSession:
    session_id: str
    line_name: str
    status: SessionStatus = SessionStatus.PENDING
    active_weights: dict[str, float] = field(default_factory=dict)
    excluded_tools: list[str] = field(default_factory=list)
    rechecked_tools: list[str] = field(default_factory=list)
    included_tools: list[str] = field(default_factory=list)
    summaries: list[DiagnosisSummary] = field(default_factory=list)
    current_summary: Optional[DiagnosisSummary] = None
    latest_report: Optional[str] = None
    chat_history: list[dict] = field(default_factory=list)
    action_log: list[UserAction] = field(default_factory=list)
    active_skill_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 非持久化字段
    tool_outputs_cache: dict[str, Any] = field(default_factory=dict, repr=False)
```

### 5.2 序列化改造

`SessionRepository` 序列化时排除 `tool_outputs_cache`：

```python
def _session_to_dict(self, session: DiagnosisSession) -> dict:
    data = session.model_dump()
    # 不序列化缓存
    data.pop("tool_outputs_cache", None)
    return data
```

---

## 6. 测试策略

### 6.1 MCP 服务测试

- 每个 MCP 服务独立的单元测试（FastAPI TestClient）
- 健康检查端点测试
- `/diagnose` 端点输入输出格式测试

### 6.2 主项目测试

- `MCPToolAdapter` HTTP 调用测试（mock httpx）
- `SkillLoader` 权重解析测试
- `DiagnoseCommand` 缓存逻辑测试
- `SessionManager` 技能权重初始化测试

### 6.3 集成测试

- 主项目 + MCP 服务的端到端测试（Docker Compose 环境）
- 排除工具后复用缓存的验证

---

## 7. 风险与回滚

| 风险 | 缓解措施 |
|------|---------|
| MCP 服务启动失败导致主项目不可用 | 增加 MCP 服务健康检查，不健康时优雅降级 |
| 技能文件格式错误导致权重解析失败 | 解析失败时使用 DEFAULT_WEIGHTS 兜底 |
| 缓存数据与最新状态不一致 | 明确缓存失效时机，切换技能/新诊断时清除 |
| Docker Compose 服务启动顺序 | 使用 `depends_on` 和 healthcheck 确保启动顺序 |

---

## 8. 实施顺序

1. **Step 1**: 创建 `mcp-services/` 目录结构，写一个 Lightning 服务验证通
2. **Step 2**: 改造 `MCPToolAdapter` 支持 HTTP 调用，配置 `lightning.yaml` 增加 url
3. **Step 3**: 迁移权重到 `comprehensive_diagnosis.md`，改造 `SkillLoader`
4. **Step 4**: 改造 `SessionManager` 从技能加载权重
5. **Step 5**: 增加 `tool_outputs_cache`，改造 `DiagnoseCommand` 缓存逻辑
6. **Step 6**: 改造 `RecheckToolCommand` 清除缓存
7. **Step 7**: 写剩余 4 个 MCP 服务
8. **Step 8**: Docker Compose 编排和集成测试
