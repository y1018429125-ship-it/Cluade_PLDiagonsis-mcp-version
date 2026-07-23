"""激活模板 Command"""

import logging
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.template_registry import TemplateRegistry
from src.domain.session_manager import SessionManager

logger = logging.getLogger(__name__)


class ActivateTemplateCommand(Command):
    """激活模板 Command"""

    def __init__(
        self,
        template_registry: TemplateRegistry,
        session_manager: SessionManager,
    ):
        self.template_registry = template_registry
        self.session_manager = session_manager

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        session = ctx.session
        template_name = ctx.intent.parameters.get("template_name") if ctx.intent else None

        if not template_name:
            raise InvalidStateError("缺少 template_name 参数")

        yield Event.thinking(session.session_id, f"激活模板: {template_name}...")

        success = self.template_registry.activate(template_name)
        if not success:
            raise InvalidStateError(f"模板 '{template_name}' 不存在或解析失败")

        session.active_template_name = template_name
        self.session_manager._persist()

        logger.info(f"模板已激活: {template_name}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"模板 '{template_name}' 已激活",
                "active_template": template_name,
            },
        )
