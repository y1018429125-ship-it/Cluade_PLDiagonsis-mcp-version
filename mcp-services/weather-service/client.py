"""HTTP client for the weather diagnosis service."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from config import BASE_URL, LOGIN_ACCOUNT, LOGIN_PASSWORD, REQUEST_TIMEOUT
from engine_models import (
    LoginResponse,
    TripInfoDataResponse,
    WeatherResponse,
)


class APIClientError(Exception):
    """Base exception for API client errors."""

    def __init__(self, message: str, code: int | str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class AuthError(APIClientError):
    """Raised when authentication fails or token is invalid."""


class DataNotFoundError(APIClientError):
    """Raised when no matching trip record is found."""


class APIClient:
    """Async HTTP client for the UHV API mock service."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = REQUEST_TIMEOUT) -> None:
        """Initialize the HTTP client.

        Args:
            base_url: Root URL of the mock API service.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def _post_form(
        self, path: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Send a POST request with form data.

        Args:
            path: API endpoint path.
            data: Form fields.

        Returns:
            Parsed JSON response.

        Raises:
            APIClientError: If the request fails or the service is unreachable.
        """
        url = f"{self.base_url}{path}"
        try:
            response = await self._client.post(url, data=data)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise APIClientError(
                "API Mock 服务未运行，请先执行 `python setup.py`"
            ) from exc
        except httpx.HTTPError as exc:
            raise APIClientError(f"HTTP 请求失败: {exc}") from exc

        try:
            return response.json()
        except Exception as exc:
            raise APIClientError("无法解析 API 响应 JSON") from exc

    async def login(self) -> str:
        """Authenticate and obtain an access token.

        Returns:
            Access token string.

        Raises:
            AuthError: If authentication fails.
        """
        payload = {
            "account": LOGIN_ACCOUNT,
            "password": LOGIN_PASSWORD,
            "accsess_token": "",
        }
        raw = await self._post_form("/tgyApiservice/userservice/login", payload)
        parsed = LoginResponse.model_validate(raw)
        if str(parsed.code) != "1001" or parsed.data is None:
            raise AuthError("认证失败，请检查 Mock 服务配置", parsed.code)
        self._token = parsed.data.access_token
        return self._token

    async def get_trip_info_data(
        self, query_date: str, line_name: str
    ) -> str:
        """Query trip records for a given date and return the matching tripId.

        Args:
            query_date: Date in YYYY-MM-DD format.
            line_name: Exact line name to match against tripLineName.

        Returns:
            Matching tripId.

        Raises:
            AuthError: If the token is invalid.
            DataNotFoundError: If no matching record is found.
        """
        if self._token is None:
            await self.login()

        payload = {
            "timeOrderBy": 1,
            "startTime": f"{query_date} 00:00:00",
            "endTime": f"{query_date} 23:59:59",
            "pressureType": 1,
            "page": 0,
            "pageSize": 999,
            "access_token": self._token,
        }
        raw = await self._post_form(
            "/tgyApiservice/devicedataservice/getTripInfoData", payload
        )
        parsed = TripInfoDataResponse.model_validate(raw)
        if str(parsed.code) == "1002":
            raise AuthError("认证已过期，请重新登录", parsed.code)
        if str(parsed.code) != "1001":
            raise APIClientError(
                f"getTripInfoData 接口返回异常: {parsed.code}", parsed.code
            )

        for record in parsed.records:
            if record.trip_line_name == line_name:
                return record.trip_id

        raise DataNotFoundError(
            f"未找到 {query_date} {line_name} 的跳闸记录"
        )

    async def get_weather(self, trip_id: str) -> WeatherResponse:
        """Fetch weather data for the trip location.

        Only the temperature (tmp) and humidity (hum) fields are consumed
        by this service.

        Args:
            trip_id: Trip identifier.

        Returns:
            Parsed getWeather response.

        Raises:
            AuthError: If the token is invalid.
        """
        if self._token is None:
            await self.login()

        payload = {"tripId": trip_id, "access_token": self._token}
        raw = await self._post_form(
            "/tgyApiservice/tripdiagnosisservice/getWeather", payload
        )
        parsed = WeatherResponse.model_validate(raw)
        if str(parsed.code) == "1002":
            raise AuthError("认证已过期，请重新登录", parsed.code)
        return parsed


async def main() -> None:
    """Quick smoke test for the client."""
    client = APIClient()
    try:
        trip_id = await client.get_trip_info_data("2025-05-08", "雅湖线")
        print(f"trip_id: {trip_id}")
        weather = await client.get_weather(trip_id)
        print(f"weather code: {weather.code}, real: {weather.data.real if weather.data else None}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
