"""Pydantic models for the wind diagnosis engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TripInfoDataRecord(BaseModel):
    """A single record returned by getTripInfoData."""

    year: str | None = None
    province: str | None = None
    voltage: str | None = None
    trip_line_name: str = Field(alias="tripLineName")
    trip_date: str | None = Field(alias="tripDate", default=None)
    trip_class: str | None = Field(alias="tripClass", default=None)
    reason1: str | None = None
    fault_phase: str | None = Field(alias="faultPhase", default=None)
    trip_tower_id: str | None = Field(alias="tripTowerID", default=None)
    reclosing_situation: str | None = Field(alias="reclosingSituation", default=None)
    trip_id: str = Field(alias="tripId")


class TripInfoDataResponse(BaseModel):
    """Response wrapper for getTripInfoData."""

    code: int | str
    data: dict[str, Any] | None = None

    @property
    def records(self) -> list[TripInfoDataRecord]:
        """Return parsed trip info data records."""
        raw = self.data.get("data") if self.data else None
        if not isinstance(raw, list):
            return []
        return [TripInfoDataRecord.model_validate(item) for item in raw]


class LoginData(BaseModel):
    """Data payload for login response."""

    access_token: str


class LoginResponse(BaseModel):
    """Response wrapper for login."""

    code: int | str
    data: LoginData | None = None


class WeatherReal(BaseModel):
    """Real-time weather data (only wind speed is consumed)."""

    ws: float


class WeatherData(BaseModel):
    """Weather payload from getWeather."""

    real: WeatherReal | None = None


class WeatherResponse(BaseModel):
    """Response wrapper for getWeather."""

    code: int | str
    data: WeatherData | None = None
