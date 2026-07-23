"""会话持久化存储

基于 JSON 文件的简单持久化实现。
使用 Pydantic v2 的 model_dump_json / model_validate_json 进行序列化。
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from src.core.models import DiagnosisSession

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = Path(os.getenv("PLDIAGNOSIS_DATA_DIR", PROJECT_ROOT / "data"))
DEFAULT_DATA_FILE = DEFAULT_DATA_DIR / "sessions.json"


class SessionRepository:
    """会话仓库 - JSON 文件持久化"""

    def __init__(self, file_path: Optional[Path] = None):
        self._file = file_path or DEFAULT_DATA_FILE
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """确保数据目录存在"""
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def save_all(self, sessions: Dict[str, DiagnosisSession]) -> None:
        """保存所有会话到 JSON 文件"""
        data = {
            "version": 1,
            "sessions": [
                sess.model_dump(mode="json") for sess in sessions.values()
            ],
        }
        temp_file = self._file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_file.replace(self._file)
            logger.info(f"持久化 {len(sessions)} 个会话到 {self._file}")
        except Exception as e:
            logger.error(f"持久化会话失败: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise

    def load_all(self) -> Dict[str, DiagnosisSession]:
        """从 JSON 文件加载所有会话"""
        if not self._file.exists():
            logger.info(f"会话文件不存在: {self._file}，返回空会话")
            return {}

        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)

            sessions = {}
            for sess_dict in data.get("sessions", []):
                try:
                    session = DiagnosisSession.model_validate(sess_dict)
                    sessions[session.session_id] = session
                except Exception as e:
                    logger.warning(f"加载会话失败，跳过: {e}")
                    continue

            logger.info(f"从 {self._file} 加载了 {len(sessions)} 个会话")
            return sessions
        except json.JSONDecodeError as e:
            logger.error(f"会话文件 JSON 格式错误: {e}")
            return {}
        except Exception as e:
            logger.error(f"加载会话失败: {e}")
            return {}

    def delete_file(self) -> None:
        """删除持久化文件（测试用）"""
        if self._file.exists():
            self._file.unlink()
            logger.info(f"删除会话文件: {self._file}")
