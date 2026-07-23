"""应用上下文"""

from src.core.models import DiagnosisContext, DiagnosisSession, ExecutionContext


class ContextBuilder:
    """上下文构建器"""

    @staticmethod
    def build(
        session: DiagnosisSession,
        user_message: str,
        **kwargs,
    ) -> ExecutionContext:
        """构建执行上下文"""
        diagnosis_ctx = DiagnosisContext(
            session_id=session.session_id,
            line_name=session.line_name,
            weights=session.active_weights.copy(),
            excluded_tools=session.excluded_tools.copy(),
            rechecked_tools=session.rechecked_tools.copy(),
        )

        return ExecutionContext(
            session=session,
            diagnosis_ctx=diagnosis_ctx,
            user_message=user_message,
            **kwargs,
        )
