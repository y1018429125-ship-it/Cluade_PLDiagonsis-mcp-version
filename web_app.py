"""Flask 应用入口

启动 PLDiagnosis 后端服务，支持优雅退出。
"""

import logging
import os
import signal
import sys
from pathlib import Path

from src.interfaces.web import create_app


def _setup_logging(log_level: str | None = None) -> None:
    """配置日志系统"""
    level = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _register_signal_handlers() -> None:
    """注册 SIGINT/SIGTERM 处理器，实现优雅退出"""

    def _graceful_exit(signum: int, _frame) -> None:
        sig_name = signal.Signals(signum).name
        logging.getLogger(__name__).info(f"收到 {sig_name}，正在优雅退出...")
        sys.exit(0)

    signal.signal(signal.SIGINT, _graceful_exit)
    signal.signal(signal.SIGTERM, _graceful_exit)


def main() -> None:
    """主入口"""
    _setup_logging()
    _register_signal_handlers()

    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")

    app = create_app()

    logging.getLogger(__name__).info(
        f"PLDiagnosis 服务启动于 http://0.0.0.0:{port} (debug={debug})"
    )
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
