"""Configuration for the lightning diagnosis HTTP service."""

from typing import Final

BASE_URL: Final[str] = "http://localhost:8000"
LOGIN_ACCOUNT: Final[str] = "yfzx"
LOGIN_PASSWORD: Final[int] = 123456
REQUEST_TIMEOUT: Final[float] = 30.0
WAVE_IMAGE_WIDTH: Final[int] = 600
WAVE_IMAGE_HEIGHT: Final[int] = 280
DECIMAL_PLACES: Final[int] = 3
