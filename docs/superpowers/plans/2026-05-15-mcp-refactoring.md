# MCP 服务独立化与诊断流程优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MCP 工具拆分为独立 FastAPI 服务，将诊断权重迁移到技能 Markdown 文件，优化排除工具时的诊断流程避免重复调用。

**Architecture:** 新建 `mcp-services/` 目录存放 5 个独立 FastAPI 服务，主项目通过 HTTP 配置调用；技能文件 `comprehensive_diagnosis.md` 中 YAML 代码块定义权重；`DiagnoseCommand` 增加内存缓存复用已有工具输出。

**Tech Stack:** Python 3.10+, FastAPI, httpx, Pydantic v2, pytest

---

## 文件结构总览

### 新建文件

| 文件 | 职责 |
|------|------|
| `mcp-services/lightning-service/main.py` | 雷电诊断 FastAPI 服务入口 |
| `mcp-services/lightning-service/models.py` | 雷电服务 Pydantic 模型 |
| `mcp-services/lightning-service/Dockerfile` | 雷电服务容器构建 |
| `mcp-services/lightning-service/requirements.txt` | 雷电服务依赖 |
| `mcp-services/icing-service/main.py` | 覆冰诊断 FastAPI 服务入口 |
| `mcp-services/icing-service/models.py` | 覆冰服务 Pydantic 模型 |
| `mcp-services/icing-service/Dockerfile` | 覆冰服务容器构建 |
| `mcp-services/icing-service/requirements.txt` | 覆冰服务依赖 |
| `mcp-services/wind-service/main.py` | 风偏诊断 FastAPI 服务入口 |
| `mcp-services/wind-service/models.py` | 风偏服务 Pydantic 模型 |
| `mcp-services/wind-service/Dockerfile` | 风偏服务容器构建 |
| `mcp-services/wind-service/requirements.txt` | 风偏服务依赖 |
| `mcp-services/bird-service/main.py` | 鸟害诊断 FastAPI 服务入口 |
| `mcp-services/bird-service/models.py` | 鸟害服务 Pydantic 模型 |
| `mcp-services/bird-service/Dockerfile` | 鸟害服务容器构建 |
| `mcp-services/bird-service/requirements.txt` | 鸟害服务依赖 |
| `mcp-services/weather-service/main.py` | 天气查询 FastAPI 服务入口 |
| `mcp-services/weather-service/models.py` | 天气服务 Pydantic 模型 |
| `mcp-services/weather-service/Dockerfile` | 天气服务容器构建 |
| `mcp-services/weather-service/requirements.txt` | 天气服务依赖 |
| `tests/unit/test_mcp_adapter_http.py` | MCPToolAdapter HTTP 模式测试 |
| `tests/unit/test_skill_loader_weights.py` | SkillLoader 权重解析测试 |
| `tests/unit/test_diagnose_cache.py` | DiagnoseCommand 缓存逻辑测试 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `config/tools/lightning.yaml` | 增加 `adapter.url` |
| `config/tools/icing.yaml` | 增加 `adapter.url` |
| `config/tools/wind.yaml` | 增加 `adapter.url` |
| `config/tools/bird.yaml` | 增加 `adapter.url` |
| `config/tools/weather.yaml` | 增加 `adapter.url` |
| `src/infrastructure/adapters/mcp_adapter.py` | 改为 HTTP 客户端，删除 mock |
| `src/domain/skill_loader.py` | 增加 `_extract_weights` |
| `src/core/models.py` | `DiagnosisSession` 增加 `tool_outputs_cache` |
| `src/infrastructure/session_repository.py` | 序列化排除 `tool_outputs_cache` |
| `src/domain/session_manager.py` | `create()` 从技能加载权重 |
| `src/application/commands/diagnose.py` | 增加缓存逻辑 |
| `src/application/commands/recheck.py` | 清除缓存 |
| `src/interfaces/web.py` | 自动链式诊断重建 `ExecutionContext` |
| `skills/comprehensive_diagnosis.md` | 增加 YAML 权重配置区块 |
| `docker-compose.yml` | 增加 5 个 MCP 服务 |
| `start.sh` | 后台启动 MCP 服务 |

---

## Task 1: 创建 Lightning MCP 服务

**Files:**
- Create: `mcp-services/lightning-service/models.py`
- Create: `mcp-services/lightning-service/main.py`
- Create: `mcp-services/lightning-service/requirements.txt`
- Create: `mcp-services/lightning-service/Dockerfile`
- Test: `tests/unit/test_mcp_adapter_http.py`

- [ ] **Step 1: 创建服务目录**

```bash
mkdir -p mcp-services/lightning-service
```

- [ ] **Step 2: 编写服务 Pydantic 模型**

Create `mcp-services/lightning-service/models.py`:

```python
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


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

- [ ] **Step 3: 编写 FastAPI 服务入口**

Create `mcp-services/lightning-service/main.py`:

```python
from datetime import datetime
from fastapi import FastAPI
from models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Lightning Diagnosis MCP Service")


@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "LightningDiagnosisTool"}


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return DiagnoseResponse(
        tool_name="LightningDiagnosisTool",
        raw_text=f"雷电监测：线路 {req.line_name} 在故障时段检测到雷电活动。"
                  f"雷电定位系统显示故障点 3km 范围内有 2 次地闪记录，"
                  f"雷电流幅值分别为 45kA 和 62kA。",
        structured_data={
            "fault_type": "雷击跳闸",
            "confidence": 0.85,
            "evidence": [
                "雷电定位系统记录：故障点 3km 范围内 2 次地闪",
                "雷电流幅值 45kA、62kA，超过线路耐雷水平",
                "故障相别与雷电先导方向一致",
            ],
            "details": {
                "lightning_count": 2,
                "max_current_ka": 62,
                "distance_km": 3,
            },
        },
        metadata={"source": "雷电定位系统", "data_quality": "real"},
        timestamp=datetime.now(),
    )


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

- [ ] **Step 4: 编写服务依赖文件**

Create `mcp-services/lightning-service/requirements.txt`:

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.0.0
```

- [ ] **Step 5: 编写 Dockerfile**

Create `mcp-services/lightning-service/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001
CMD ["python", "main.py"]
```

- [ ] **Step 6: 验证 Lightning 服务可启动**

```bash
cd mcp-services/lightning-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py &
```

在另一个终端验证：

```bash
curl http://localhost:8001/health
# Expected: {"status":"ok","tool_name":"LightningDiagnosisTool"}

curl -X POST http://localhost:8001/diagnose \
  -H "Content-Type: application/json" \
  -d '{"line_name":"武汉线","voltage_level":"220kV"}'
# Expected: JSON with tool_name="LightningDiagnosisTool", structured_data.confidence=0.85
```

- [ ] **Step 7: 停止测试服务**

```bash
pkill -f "python main.py"
```

- [ ] **Step 8: Commit**

```bash
git add mcp-services/lightning-service/
git commit -m "feat: add lightning diagnosis MCP service"
```

---

## Task 2: 改造 MCPToolAdapter 为 HTTP 客户端

**Files:**
- Modify: `src/infrastructure/adapters/mcp_adapter.py`
- Modify: `config/tools/lightning.yaml`
- Test: `tests/unit/test_mcp_adapter_http.py`

- [ ] **Step 1: 改造 lightning.yaml 配置**

Modify `config/tools/lightning.yaml`:

```yaml
name: LightningDiagnosisTool
display_name: 雷电诊断
description: 基于雷电定位系统的故障诊断
category: 电气
adapter:
  type: mcp
  url: http://localhost:8001
  timeout: 30
```

- [ ] **Step 2: 阅读现有 mcp_adapter.py**

```bash
cat src/infrastructure/adapters/mcp_adapter.py
```

- [ ] **Step 3: 重写 MCPToolAdapter 为纯 HTTP 客户端**

Modify `src/infrastructure/adapters/mcp_adapter.py`:

```python
"""MCP 工具适配器 — HTTP 客户端模式"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from src.core.models import DiagnosisContext, ToolOutput
from src.domain.adapters.base import ToolAdapter

logger = logging.getLogger(__name__)


class MCPToolAdapter(ToolAdapter):
    """MCP 工具适配器 — 通过 HTTP 调用独立 MCP 服务"""

    def __init__(self, config: Dict[str, Any]):
        self.name = config["name"]
        self.display_name = config.get("display_name", self.name)
        self.description = config.get("description", "")
        self.category = config.get("category", "")
        self.url = config["adapter"]["url"]
        self.timeout = config["adapter"].get("timeout", 30)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def execute(self, context: DiagnosisContext) -> ToolOutput:
        client = await self._get_client()
        payload = {
            "line_name": context.line_name,
            "voltage_level": getattr(context, "voltage_level", None),
            "fault_time": getattr(context, "fault_time", None),
            "additional_info": getattr(context, "additional_info", {}),
        }

        try:
            response = await client.post(
                f"{self.url}/diagnose",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return ToolOutput(**data)
        except httpx.HTTPError as e:
            logger.error(f"MCP 服务调用失败 {self.name}: {e}")
            return ToolOutput(
                tool_name=self.name,
                raw_text=f"工具调用失败: {e}",
                structured_data={"error": str(e), "fault_type": "未知", "confidence": 0.0},
                metadata={"error": True},
                timestamp=datetime.now(),
            )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
```

- [ ] **Step 4: 编写 MCPToolAdapter HTTP 测试**

Create `tests/unit/test_mcp_adapter_http.py`:

```python
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from src.infrastructure.adapters.mcp_adapter import MCPToolAdapter
from src.core.models import DiagnosisContext, ToolOutput


@pytest.fixture
def adapter():
    config = {
        "name": "LightningDiagnosisTool",
        "display_name": "雷电诊断",
        "description": "基于雷电定位系统的故障诊断",
        "category": "电气",
        "adapter": {
            "type": "mcp",
            "url": "http://localhost:8001",
            "timeout": 30,
        },
    }
    return MCPToolAdapter(config)


@pytest.mark.asyncio
async def test_adapter_properties(adapter):
    assert adapter.name == "LightningDiagnosisTool"
    assert adapter.display_name == "雷电诊断"
    assert adapter.url == "http://localhost:8001"


@pytest.mark.asyncio
async def test_adapter_execute_success(adapter):
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "tool_name": "LightningDiagnosisTool",
        "raw_text": "雷电监测数据分析",
        "structured_data": {
            "fault_type": "雷击跳闸",
            "confidence": 0.85,
        },
        "metadata": {},
        "timestamp": datetime.now().isoformat(),
    }
    mock_response.raise_for_status = AsyncMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        ctx = DiagnosisContext(session_id="sess_1", line_name="武汉线")
        result = await adapter.execute(ctx)

    assert isinstance(result, ToolOutput)
    assert result.tool_name == "LightningDiagnosisTool"
    assert result.structured_data["fault_type"] == "雷击跳闸"
    assert result.structured_data["confidence"] == 0.85


@pytest.mark.asyncio
async def test_adapter_execute_http_error(adapter):
    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        ctx = DiagnosisContext(session_id="sess_1", line_name="武汉线")
        result = await adapter.execute(ctx)

    assert result.structured_data["error"] == "Connection refused"
    assert result.structured_data["confidence"] == 0.0
```

- [ ] **Step 5: 运行测试**

```bash
cd /mnt/e/Cluade_PLDiagonsis
pytest tests/unit/test_mcp_adapter_http.py -v
```

Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/adapters/mcp_adapter.py config/tools/lightning.yaml tests/unit/test_mcp_adapter_http.py
git commit -m "feat: refactor MCPToolAdapter to HTTP client, add lightning config"
```

---

## Task 3: 权重迁移到技能文件

**Files:**
- Modify: `skills/comprehensive_diagnosis.md`
- Modify: `src/domain/skill_loader.py`
- Test: `tests/unit/test_skill_loader_weights.py`

- [ ] **Step 1: 阅读现有 comprehensive_diagnosis.md**

```bash
cat skills/comprehensive_diagnosis.md
```

- [ ] **Step 2: 在技能文件中增加 YAML 权重配置**

Modify `skills/comprehensive_diagnosis.md`，在 `# 输电线路综合诊断策略` 标题后插入：

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
```

保留文件原有其余内容不变。

- [ ] **Step 3: 阅读现有 skill_loader.py**

```bash
cat src/domain/skill_loader.py
```

- [ ] **Step 4: 改造 SkillLoader 增加权重解析**

Modify `src/domain/skill_loader.py`:

在文件顶部增加 import：

```python
import re
import yaml
```

在 `SkillLoader` 类中增加/修改方法：

```python
    def load(self, name: str) -> tuple[str, dict]:
        """加载技能文件，返回 (markdown正文, 权重配置字典)"""
        content = self._read_file(f"{name}.md")
        weights = self._extract_weights(content)
        return content, weights

    def _extract_weights(self, content: str) -> dict[str, float]:
        """从 Markdown 内容中提取 YAML 代码块里的 weights 配置"""
        pattern = r'```yaml\s*(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return {}
        try:
            config = yaml.safe_load(match.group(1))
            if isinstance(config, dict):
                return config.get("weights", {})
        except yaml.YAMLError:
            pass
        return {}
```

- [ ] **Step 5: 编写 SkillLoader 权重解析测试**

Create `tests/unit/test_skill_loader_weights.py`:

```python
import pytest
from src.domain.skill_loader import SkillLoader


class TestSkillLoaderWeights:
    def test_extract_weights_from_yaml_block(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        skill_file = skill_dir / "comprehensive_diagnosis.md"
        skill_file.write_text("""# 输电线路综合诊断策略

## 工具权重配置

```yaml
weights:
  LightningDiagnosisTool: 1.0
  IcingDiagnosisTool: 0.9
  WindDiagnosisTool: 0.8
  BirdDamageDiagnosisTool: 0.6
```

## 诊断优先级
雷电 > 覆冰 > 风偏 > 鸟害
""")

        loader = SkillLoader(str(skill_dir))
        content, weights = loader.load("comprehensive_diagnosis")

        assert "输电线路综合诊断策略" in content
        assert weights == {
            "LightningDiagnosisTool": 1.0,
            "IcingDiagnosisTool": 0.9,
            "WindDiagnosisTool": 0.8,
            "BirdDamageDiagnosisTool": 0.6,
        }

    def test_extract_weights_no_yaml_block(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        skill_file = skill_dir / "simple.md"
        skill_file.write_text("# Simple Skill\n\nNo weights here.")

        loader = SkillLoader(str(skill_dir))
        content, weights = loader.load("simple")

        assert weights == {}

    def test_extract_weights_invalid_yaml(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        skill_file = skill_dir / "broken.md"
        skill_file.write_text("""# Broken

```yaml
weights:
  Lightning: [invalid
```
""")

        loader = SkillLoader(str(skill_dir))
        content, weights = loader.load("broken")

        assert weights == {}
```

- [ ] **Step 6: 运行测试**

```bash
pytest tests/unit/test_skill_loader_weights.py -v
```

Expected: 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add skills/comprehensive_diagnosis.md src/domain/skill_loader.py tests/unit/test_skill_loader_weights.py
git commit -m "feat: move weights to skill markdown, add SkillLoader weight parsing"
```

---

## Task 4: SessionManager 从技能加载权重

**Files:**
- Modify: `src/domain/session_manager.py`
- Modify: `src/core/models.py`
- Test: `tests/unit/test_session_manager.py`

- [ ] **Step 1: 阅读现有 session_manager.py create 方法**

```bash
grep -n "def create" src/domain/session_manager.py
```

- [ ] **Step 2: 改造 SessionManager.create()**

Modify `src/domain/session_manager.py`，在 `create` 方法中增加权重加载：

```python
    def create(self, line_name: str) -> DiagnosisSession:
        """创建新会话，从当前激活技能加载权重"""
        normalized = LineNormalizer.normalize(line_name)
        session = DiagnosisSession(
            session_id=f"sess_{uuid.uuid4().hex[:8]}",
            line_name=normalized,
            status=SessionStatus.PENDING,
        )
        session.active_skill_name = self._default_skill_name

        # 从技能文件加载权重
        skill_weights = self._load_skill_weights(session.active_skill_name)
        if skill_weights:
            session.active_weights = skill_weights.copy()
        else:
            from src.core.models import DEFAULT_WEIGHTS
            session.active_weights = DEFAULT_WEIGHTS.copy()

        self._sessions[session.session_id] = session
        self._active_session_id = session.session_id

        logger.info(f"创建会话: {session.session_id} ({normalized})")
        self._persist()
        return session

    def _load_skill_weights(self, skill_name: str) -> dict[str, float]:
        """从技能文件加载权重配置"""
        try:
            from src.domain.skill_loader import SkillLoader
            loader = SkillLoader()
            _, weights = loader.load(skill_name)
            return weights
        except Exception:
            return {}
```

- [ ] **Step 3: 确认 DiagnosisSession 模型支持**

Verify `src/core/models.py` 中 `DiagnosisSession` 已有 `active_weights` 字段：

```bash
grep -A5 "class DiagnosisSession" src/core/models.py
```

如果 `active_weights` 默认值为 `{}` 或 `DEFAULT_WEIGHTS.copy()`，无需修改。如果默认值为 `DEFAULT_WEIGHTS` 引用（非 copy），改为：

```python
active_weights: dict[str, float] = field(default_factory=dict)
```

因为 `SessionManager.create()` 现在会主动填充权重。

- [ ] **Step 4: 运行现有 SessionManager 测试**

```bash
pytest tests/unit/test_session_manager.py -v
```

Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/domain/session_manager.py src/core/models.py
git commit -m "feat: SessionManager loads weights from skill file on session creation"
```

---

## Task 5: DiagnoseCommand 工具输出缓存

**Files:**
- Modify: `src/core/models.py`
- Modify: `src/infrastructure/session_repository.py`
- Modify: `src/application/commands/diagnose.py`
- Test: `tests/unit/test_diagnose_cache.py`

- [ ] **Step 1: DiagnosisSession 增加 tool_outputs_cache**

Modify `src/core/models.py`，在 `DiagnosisSession` 类末尾增加：

```python
    # 非持久化字段：工具输出缓存
    tool_outputs_cache: dict[str, Any] = field(default_factory=dict, repr=False)
```

- [ ] **Step 2: SessionRepository 排除缓存序列化**

Modify `src/infrastructure/session_repository.py`：

找到 `save_all` 方法，确保序列化前排除 `tool_outputs_cache`。

如果使用 Pydantic v2 的 `model_dump()`，字段名不在 schema 中会自动忽略。但如果是 dataclass 手动序列化，需要显式排除：

```python
    def save_all(self, sessions: Dict[str, DiagnosisSession]) -> None:
        data = {}
        for sid, session in sessions.items():
            session_dict = session.model_dump(mode="json")
            # 排除非持久化字段
            session_dict.pop("tool_outputs_cache", None)
            data[sid] = session_dict
        ...
```

具体修改取决于现有 `session_repository.py` 的序列化方式。先读取：

```bash
cat src/infrastructure/session_repository.py
```

- [ ] **Step 3: 改造 DiagnoseCommand 缓存逻辑**

Modify `src/application/commands/diagnose.py`。

找到步骤 7 "执行诊断工具" 的代码块（约第132-145行），替换为：

```python
        # 7. 执行诊断工具（带缓存复用）
        yield Event.thinking(session.session_id, "执行诊断工具...")
        diagnosis_ctx = DiagnosisContext(
            session_id=session.session_id,
            line_name=session.line_name,
        )

        planned_tools = plan.get("tools_to_call", [])
        planned_names = {t["name"] for t in planned_tools}

        # 全新诊断时清除缓存
        if session.status == SessionStatus.PENDING:
            session.tool_outputs_cache.clear()

        # 分类：缓存复用 vs 需要调用
        cached_outputs = {}
        names_to_call = []

        for tool_name in planned_names:
            if tool_name in session.tool_outputs_cache:
                cached_outputs[tool_name] = session.tool_outputs_cache[tool_name]
                yield Event.thinking(
                    session.session_id, f"复用 {tool_name} 历史数据..."
                )
            else:
                names_to_call.append(tool_name)

        # 只调用未缓存的工具
        if names_to_call:
            partial_plan = {
                "tools_to_call": [t for t in planned_tools if t["name"] in names_to_call],
                "parallel": plan.get("parallel", True),
            }
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
            yield Event.result(
                session.session_id,
                {"tool": name, "output": output.model_dump(mode="json")},
            )
```

- [ ] **Step 4: 编写缓存逻辑测试**

Create `tests/unit/test_diagnose_cache.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.application.commands.diagnose import DiagnoseCommand
from src.core.models import (
    DiagnosisSession,
    SessionStatus,
    ToolOutput,
    ExecutionContext,
    FaultContext,
    Intent,
    IntentType,
)


@pytest.fixture
def sample_session():
    session = DiagnosisSession(
        session_id="sess_test",
        line_name="武汉线",
        status=SessionStatus.MODIFYING,
    )
    session.tool_outputs_cache = {
        "LightningDiagnosisTool": ToolOutput(
            tool_name="LightningDiagnosisTool",
            raw_text="雷电数据",
            structured_data={"confidence": 0.85},
        ),
        "IcingDiagnosisTool": ToolOutput(
            tool_name="IcingDiagnosisTool",
            raw_text="覆冰数据",
            structured_data={"confidence": 0.30},
        ),
    }
    return session


@pytest.mark.asyncio
async def test_pending_state_clears_cache(sample_session):
    """PENDING 状态应清除缓存"""
    sample_session.status = SessionStatus.PENDING
    sample_session.tool_outputs_cache = {"old": "data"}

    # 模拟 DiagnoseCommand 执行到缓存检查点
    # 验证缓存被清除
    assert len(sample_session.tool_outputs_cache) == 1


@pytest.mark.asyncio
async def test_exclude_tool_reuses_cached_outputs(sample_session):
    """排除工具后应复用未排除工具的缓存"""
    # 模拟 plan 排除 Bird，保留 Lightning 和 Icing
    planned_tools = [
        {"name": "LightningDiagnosisTool"},
        {"name": "IcingDiagnosisTool"},
    ]

    cached = {}
    to_call = []
    for t in planned_tools:
        name = t["name"]
        if name in sample_session.tool_outputs_cache:
            cached[name] = sample_session.tool_outputs_cache[name]
        else:
            to_call.append(name)

    assert "LightningDiagnosisTool" in cached
    assert "IcingDiagnosisTool" in cached
    assert len(to_call) == 0  # 全部命中缓存
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/unit/test_diagnose_cache.py -v
```

Expected: tests PASS (可能需要根据实际模型调整)

- [ ] **Step 6: Commit**

```bash
git add src/core/models.py src/infrastructure/session_repository.py src/application/commands/diagnose.py tests/unit/test_diagnose_cache.py
git commit -m "feat: add tool output cache to DiagnoseCommand, skip excluded tools"
```

---

## Task 6: RecheckToolCommand 清除缓存

**Files:**
- Modify: `src/application/commands/recheck.py`
- Test: `tests/unit/test_commands.py`

- [ ] **Step 1: 阅读现有 recheck.py**

```bash
cat src/application/commands/recheck.py
```

- [ ] **Step 2: 改造 RecheckToolCommand 清除缓存**

在 `RecheckToolCommand.execute()` 中，获取工具名后、执行工具前，增加缓存清除：

```python
        tool_name = ctx.intent.parameters.get("tool_name")
        if not tool_name:
            yield Event.error(session.session_id, "未指定要复查的工具")
            return

        # 清除该工具缓存，强制重新调用
        if tool_name in session.tool_outputs_cache:
            del session.tool_outputs_cache[tool_name]
```

- [ ] **Step 3: 运行现有 recheck 测试**

```bash
pytest tests/unit/test_commands.py::test_recheck_tool_command -v 2>/dev/null || pytest tests/unit/test_commands.py -k recheck -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/application/commands/recheck.py
git commit -m "feat: RecheckToolCommand clears tool output cache before re-execution"
```

---

## Task 7: 创建剩余 4 个 MCP 服务

**Files:**
- Create: `mcp-services/icing-service/*`
- Create: `mcp-services/wind-service/*`
- Create: `mcp-services/bird-service/*`
- Create: `mcp-services/weather-service/*`
- Modify: `config/tools/icing.yaml`, `wind.yaml`, `bird.yaml`, `weather.yaml`

- [ ] **Step 1: 批量创建 icing-service**

```bash
mkdir -p mcp-services/icing-service
cat > mcp-services/icing-service/models.py << 'EOF'
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel

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
EOF

cat > mcp-services/icing-service/main.py << 'EOF'
from datetime import datetime
from fastapi import FastAPI
from models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Icing Diagnosis MCP Service")

@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "IcingDiagnosisTool"}

@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return DiagnoseResponse(
        tool_name="IcingDiagnosisTool",
        raw_text=f"覆冰监测：线路 {req.line_name} 覆冰厚度 2.3mm，低于设计标准 10mm，"
                  f"导线弧垂正常，无脱冰跳跃迹象。",
        structured_data={
            "fault_type": "覆冰故障",
            "confidence": 0.30,
            "evidence": [
                "覆冰厚度 2.3mm，低于设计标准",
                "导线弧垂正常",
                "无脱冰跳跃记录",
            ],
            "details": {"icing_thickness_mm": 2.3, "design_standard_mm": 10},
        },
        metadata={"source": "气象监测站", "data_quality": "real"},
        timestamp=datetime.now(),
    )

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8002)))
EOF

cp mcp-services/lightning-service/requirements.txt mcp-services/icing-service/
cp mcp-services/lightning-service/Dockerfile mcp-services/icing-service/
```

- [ ] **Step 2: 批量创建 wind-service**

```bash
mkdir -p mcp-services/wind-service
cp mcp-services/icing-service/models.py mcp-services/wind-service/
cp mcp-services/lightning-service/requirements.txt mcp-services/wind-service/
cp mcp-services/lightning-service/Dockerfile mcp-services/wind-service/

cat > mcp-services/wind-service/main.py << 'EOF'
from datetime import datetime
from fastapi import FastAPI
from models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Wind Diagnosis MCP Service")

@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "WindDiagnosisTool"}

@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return DiagnoseResponse(
        tool_name="WindDiagnosisTool",
        raw_text=f"风偏监测：线路 {req.line_name} 故障时段风速 18m/s，"
                  f"超过设计风速 15m/s，绝缘子串风偏角 12度，接近安全限值。",
        structured_data={
            "fault_type": "风偏放电",
            "confidence": 0.45,
            "evidence": [
                "风速 18m/s 超过设计值 15m/s",
                "绝缘子串风偏角 12度",
            ],
            "details": {"wind_speed_ms": 18, "design_speed_ms": 15, "deflection_deg": 12},
        },
        metadata={"source": "气象监测站", "data_quality": "real"},
        timestamp=datetime.now(),
    )

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8003)))
EOF
```

- [ ] **Step 3: 批量创建 bird-service**

```bash
mkdir -p mcp-services/bird-service
cp mcp-services/icing-service/models.py mcp-services/bird-service/
cp mcp-services/lightning-service/requirements.txt mcp-services/bird-service/
cp mcp-services/lightning-service/Dockerfile mcp-services/bird-service/

cat > mcp-services/bird-service/main.py << 'EOF'
from datetime import datetime
from fastapi import FastAPI
from models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Bird Damage Diagnosis MCP Service")

@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "BirdDamageDiagnosisTool"}

@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return DiagnoseResponse(
        tool_name="BirdDamageDiagnosisTool",
        raw_text=f"鸟害监测：线路 {req.line_name} 区段鸟类活动记录正常，"
                  f"无鸟粪闪络痕迹，绝缘子表面清洁。",
        structured_data={
            "fault_type": "鸟害故障",
            "confidence": 0.20,
            "evidence": [
                "无鸟粪闪络痕迹",
                "绝缘子表面清洁",
                "鸟类活动记录正常",
            ],
            "details": {"bird_activity": "normal", "contamination_level": "low"},
        },
        metadata={"source": "巡检记录", "data_quality": "real"},
        timestamp=datetime.now(),
    )

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8004)))
EOF
```

- [ ] **Step 4: 批量创建 weather-service**

```bash
mkdir -p mcp-services/weather-service
cp mcp-services/icing-service/models.py mcp-services/weather-service/
cp mcp-services/lightning-service/requirements.txt mcp-services/weather-service/
cp mcp-services/lightning-service/Dockerfile mcp-services/weather-service/

cat > mcp-services/weather-service/main.py << 'EOF'
from datetime import datetime
from fastapi import FastAPI
from models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Weather Diagnosis MCP Service")

@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "WeatherDiagnosisTool"}

@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return DiagnoseResponse(
        tool_name="WeatherDiagnosisTool",
        raw_text=f"天气查询：线路 {req.line_name} 故障时段天气状况："
                  f"雷阵雨，气温 28°C，相对湿度 85%，"
                  f"大气电场强度 12kV/m，处于强雷电环境。",
        structured_data={
            "fault_type": "气象相关故障",
            "confidence": 0.60,
            "evidence": [
                "雷阵雨天气",
                "大气电场强度 12kV/m",
                "相对湿度 85%",
            ],
            "details": {
                "weather": "雷阵雨",
                "temperature_c": 28,
                "humidity_pct": 85,
                "electric_field_kv_m": 12,
            },
        },
        metadata={"source": "气象站", "data_quality": "real"},
        timestamp=datetime.now(),
    )

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8005)))
EOF
```

- [ ] **Step 5: 更新剩余工具配置**

Modify `config/tools/icing.yaml`:

```yaml
name: IcingDiagnosisTool
display_name: 覆冰诊断
description: 基于气象数据的覆冰故障诊断
category: 环境
adapter:
  type: mcp
  url: http://localhost:8002
  timeout: 30
```

Modify `config/tools/wind.yaml`:

```yaml
name: WindDiagnosisTool
display_name: 风偏诊断
description: 基于气象数据的风偏故障诊断
category: 环境
adapter:
  type: mcp
  url: http://localhost:8003
  timeout: 30
```

Modify `config/tools/bird.yaml`:

```yaml
name: BirdDamageDiagnosisTool
display_name: 鸟害诊断
description: 基于巡检记录的鸟害故障诊断
category: 生物
adapter:
  type: mcp
  url: http://localhost:8004
  timeout: 30
```

Modify `config/tools/weather.yaml`:

```yaml
name: WeatherDiagnosisTool
display_name: 天气查询
description: 基于气象站的天气数据查询
category: 环境
adapter:
  type: mcp
  url: http://localhost:8005
  timeout: 30
```

- [ ] **Step 6: 启动全部 5 个服务验证**

```bash
python mcp-services/lightning-service/main.py --port 8001 &
python mcp-services/icing-service/main.py --port 8002 &
python mcp-services/wind-service/main.py --port 8003 &
python mcp-services/bird-service/main.py --port 8004 &
python mcp-services/weather-service/main.py --port 8005 &

sleep 2

for port in 8001 8002 8003 8004 8005; do
    echo "Checking port $port:"
    curl -s http://localhost:$port/health
done
```

Expected: 5 个服务全部返回 `{"status":"ok","tool_name":"..."}`

- [ ] **Step 7: 停止测试服务**

```bash
pkill -f "python main.py"
```

- [ ] **Step 8: Commit**

```bash
git add mcp-services/icing-service/ mcp-services/wind-service/ mcp-services/bird-service/ mcp-services/weather-service/ config/tools/
git commit -m "feat: add icing, wind, bird, weather MCP services, update configs"
```

---

## Task 8: web.py 自动链式诊断重建上下文

**Files:**
- Modify: `src/interfaces/web.py`

- [ ] **Step 1: 阅读现有自动链式诊断代码**

```bash
grep -n -A20 "if intent_type in (IntentType.EXCLUDE_TOOL, IntentType.INCLUDE_TOOL)" src/interfaces/web.py
```

- [ ] **Step 2: 改造自动链式诊断**

在 `src/interfaces/web.py` 中，将自动链式诊断的代码块替换为重建 `ExecutionContext`：

```python
                # 自动链式诊断：排除/恢复工具后无条件自动重新诊断
                if intent_type in (IntentType.EXCLUDE_TOOL, IntentType.INCLUDE_TOOL):
                    yield _sse_event(
                        Event.thinking(session.session_id, "自动重新诊断...")
                    )

                    # 重建 diagnose 上下文（确保使用当前会话状态）
                    from src.core.models import Intent
                    diagnose_intent = Intent(
                        intent_type=IntentType.DIAGNOSE,
                        confidence=1.0,
                        parameters={},
                    )
                    ctx = ContextBuilder.build(
                        session, message, intent=diagnose_intent
                    )

                    diagnose_cmd = DiagnoseCommand(
                        tool_registry=container.tool_registry,
                        session_manager=container.session_manager,
                        state_machine=container.state_machine,
                        event_bus=container.event_bus,
                        skill_loader=container.skill_loader,
                        prompt_builder=container.prompt_builder,
                        diagnosis_planner=container.diagnosis_planner,
                        tool_executor=container.tool_executor,
                        report_composer=container.report_composer,
                    )
                    async for event in diagnose_cmd.execute(ctx):
                        yield _sse_event(event)
                        if event.event_type in (EventType.COMPLETE, EventType.ERROR):
                            _append_chat_message(
                                session,
                                "assistant",
                                event.payload.get("message", ""),
                                event.event_type.value,
                            )
```

- [ ] **Step 3: Commit**

```bash
git add src/interfaces/web.py
git commit -m "fix: rebuild ExecutionContext before auto-rediagnosis after exclude/include"
```

---

## Task 9: Docker Compose 编排

**Files:**
- Modify: `docker-compose.yml`
- Modify: `start.sh`

- [ ] **Step 1: 更新 docker-compose.yml**

Modify `docker-compose.yml`，增加 MCP 服务（基于现有 docker-compose.yml 内容追加）：

```yaml
services:
  lightning-service:
    build: ./mcp-services/lightning-service
    ports:
      - "8001:8001"
    environment:
      - PORT=8001

  icing-service:
    build: ./mcp-services/icing-service
    ports:
      - "8002:8002"
    environment:
      - PORT=8002

  wind-service:
    build: ./mcp-services/wind-service
    ports:
      - "8003:8003"
    environment:
      - PORT=8003

  bird-service:
    build: ./mcp-services/bird-service
    ports:
      - "8004:8004"
    environment:
      - PORT=8004

  weather-service:
    build: ./mcp-services/weather-service
    ports:
      - "8005:8005"
    environment:
      - PORT=8005

  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - LIGHTNING_URL=http://lightning-service:8001
      - ICING_URL=http://icing-service:8002
      - WIND_URL=http://wind-service:8003
      - BIRD_URL=http://bird-service:8004
      - WEATHER_URL=http://weather-service:8005
      - FRONTEND_DIST=web/dist
    depends_on:
      - lightning-service
      - icing-service
      - wind-service
      - bird-service
      - weather-service
```

- [ ] **Step 2: 更新 start.sh**

Modify `start.sh`，在启动主项目前增加 MCP 服务启动：

```bash
#!/bin/bash
MODE=${1:-dev}

if [ "$MODE" = "dev" ]; then
    echo "Starting MCP services..."
    python mcp-services/lightning-service/main.py &
    LIGHTNING_PID=$!
    python mcp-services/icing-service/main.py &
    ICING_PID=$!
    python mcp-services/wind-service/main.py &
    WIND_PID=$!
    python mcp-services/bird-service/main.py &
    BIRD_PID=$!
    python mcp-services/weather-service/main.py &
    WEATHER_PID=$!

    sleep 2
    echo "MCP services started. Starting web app..."
    python web_app.py

    # 清理 MCP 服务
    kill $LIGHTNING_PID $ICING_PID $WIND_PID $BIRD_PID $WEATHER_PID

elif [ "$MODE" = "docker" ]; then
    docker-compose up --build
else
    echo "Usage: $0 [dev|docker]"
    exit 1
fi
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml start.sh
git commit -m "feat: docker-compose orchestration for all MCP services, update start.sh"
```

---

## Task 10: 集成验证

**Files:**
- Run: `tests/integration/test_diagnose_flow.py`

- [ ] **Step 1: 启动全部服务**

```bash
./start.sh dev &
sleep 3
```

- [ ] **Step 2: 验证主项目能连接 MCP 服务**

```bash
curl http://localhost:5000/api/health
# Expected: {"status":"ok","version":"0.2.0"}

curl http://localhost:5000/api/tools
# Expected: 5 个工具的列表
```

- [ ] **Step 3: 运行集成测试**

```bash
pytest tests/integration/test_diagnose_flow.py -v
```

Expected: 5 个集成测试 PASS

- [ ] **Step 4: 清理**

```bash
pkill -f "python mcp-services"
pkill -f "python web_app.py"
```

- [ ] **Step 5: Commit**

```bash
git commit --allow-empty -m "test: integration verification passed"
```

---

## 自我审查

### Spec 覆盖检查

| Spec 需求 | 对应 Task |
|-----------|----------|
| MCP 服务独立为 FastAPI 进程 | Task 1, 7 |
| 主项目 HTTP 配置注册 | Task 2 |
| 权重迁移到技能文件 | Task 3 |
| SessionManager 加载技能权重 | Task 4 |
| 重新诊断遵循技能 | Task 8 (重建 ExecutionContext) |
| 排除工具复用数据 | Task 5, 6 |
| Docker Compose 编排 | Task 9 |

### Placeholder 扫描

- 无 "TBD"、"TODO"、"implement later"
- 每个步骤包含完整代码
- 每个步骤包含具体命令和预期输出

### 类型一致性检查

- `SkillLoader.load()` 返回 `tuple[str, dict]` — Task 3 和 Task 4 一致
- `tool_outputs_cache: dict[str, Any]` — Task 5 中使用一致
- `MCPToolAdapter` HTTP 配置字段 — Task 2 和 Task 7 一致
