"""自定义异常体系"""


class PLDiagnosisError(Exception):
    """基类异常"""
    code: str = "UNKNOWN_ERROR"
    status_code: int = 500

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidStateError(PLDiagnosisError):
    """无效状态转换"""
    code = "INVALID_STATE"
    status_code = 400


class SessionNotFoundError(PLDiagnosisError):
    """会话不存在"""
    code = "SESSION_NOT_FOUND"
    status_code = 404


class ToolNotFoundError(PLDiagnosisError):
    """工具不存在"""
    code = "TOOL_NOT_FOUND"
    status_code = 404


class ToolExecutionError(PLDiagnosisError):
    """工具执行失败"""
    code = "TOOL_EXECUTION_FAILED"
    status_code = 502


class IntentClassificationError(PLDiagnosisError):
    """意图识别失败"""
    code = "INTENT_CLASSIFICATION_FAILED"
    status_code = 500


class WeightValidationError(PLDiagnosisError):
    """权重验证失败"""
    code = "WEIGHT_VALIDATION_FAILED"
    status_code = 400


class TemplateParseError(PLDiagnosisError):
    """模板解析失败"""
    code = "TEMPLATE_PARSE_ERROR"
    status_code = 400


class StrategyNotFoundError(PLDiagnosisError):
    """策略不存在"""
    code = "STRATEGY_NOT_FOUND"
    status_code = 404


class LLMServiceError(PLDiagnosisError):
    """LLM 服务错误"""
    code = "LLM_SERVICE_ERROR"
    status_code = 503


class MCPConnectionError(PLDiagnosisError):
    """MCP 连接错误"""
    code = "MCP_CONNECTION_ERROR"
    status_code = 503


class ConfigLoadError(PLDiagnosisError):
    """配置加载错误"""
    code = "CONFIG_LOAD_ERROR"
    status_code = 500
