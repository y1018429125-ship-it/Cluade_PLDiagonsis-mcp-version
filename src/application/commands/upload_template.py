"""上传模板 Command"""

import logging
from pathlib import Path
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext
from src.core.exceptions import InvalidStateError
from src.application.commands.base import Command
from src.domain.template_registry import TemplateRegistry

logger = logging.getLogger(__name__)


class UploadTemplateCommand(Command):
    """上传模板 Command"""

    def __init__(self, template_registry: TemplateRegistry):
        self.template_registry = template_registry

    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        session = ctx.session
        file_path = ctx.intent.parameters.get("file_path") if ctx.intent else None
        original_name = ctx.intent.parameters.get("original_name") if ctx.intent else None

        if not file_path or not original_name:
            raise InvalidStateError("缺少文件路径或文件名")

        yield Event.thinking(session.session_id, f"上传模板: {original_name}...")

        result = self.template_registry.upload(Path(file_path), original_name)

        logger.info(f"模板上传完成: {result['name']}")

        yield Event.complete(
            session.session_id,
            {
                "message": f"模板 '{result['name']}' 上传成功",
                "template": result,
            },
        )
