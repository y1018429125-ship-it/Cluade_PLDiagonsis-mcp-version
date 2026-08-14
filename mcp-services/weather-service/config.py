"""Configuration for the weather diagnosis HTTP service."""

from typing import Final

BASE_URL: Final[str] = "http://localhost:8000"
LOGIN_ACCOUNT: Final[str] = "YFZX-2"
LOGIN_PASSWORD: Final[int] = 123456
REQUEST_TIMEOUT: Final[float] = 30.0
DECIMAL_PLACES: Final[int] = 3
