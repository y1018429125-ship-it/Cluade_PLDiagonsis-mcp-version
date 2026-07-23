"""Pydantic models for the lightning diagnosis engine."""

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


class Eigenvalue(BaseModel):
    """Waveform eigenvalue from getTripDiagnosis."""

    amplitude: float
    half_peak_time: float = Field(alias="halfPeakTime")


class TripDiagnosisData(BaseModel):
    """Probability data from getTripDiagnosis."""

    is_lightning: float = Field(alias="isLightning")
    no_lightning: float = Field(alias="noLightning")
    round_pass: float = Field(alias="roundPass")
    back_pass: float = Field(alias="backPass")


class TripDiagnosisResponse(BaseModel):
    """Response wrapper for getTripDiagnosis."""

    code: int | str
    data: TripDiagnosisData | None = None
    process: str | None = None
    eigenvalue: Eigenvalue | None = None
    msg: str | None = None


class FlashRecord(BaseModel):
    """A single lightning flash record from getTripInfo."""

    sequence: int
    peak_current: float = Field(alias="peakCurrent")
    longitude: float
    latitude: float
    timedate: str
    str_mltiplicity: str = Field(alias="strMltiplicity")
    tdf_string: str = Field(alias="tdfString")
    tdf_sum: int = Field(alias="tdfsum")
    distance: int | None = None
    tower: str | None = None


class TripInfoTrip(BaseModel):
    """Trip details from getTripInfo."""

    line_name: str = Field(alias="linename")
    pressure: str
    timedate: str
    milli_second: str | int | None = Field(alias="milliSecond", default=None)
    tower_id: str = Field(alias="towerId")
    longitude: float
    latitude: float
    trip_cause: str = Field(alias="tripCause")
    trip_class: str = Field(alias="tripClass")
    trip_phase: str = Field(alias="tripPhase")
    trip_station1: str = Field(alias="tripStation1")
    trip_diaelepo1: str = Field(alias="tripDiaelepo1")
    trip_station2: str = Field(alias="tripStation2")
    trip_diaelepo2: str = Field(alias="tripDiaelepo2")
    trip_description: str = Field(alias="tripDescription")


class TripInfoResponse(BaseModel):
    """Response wrapper for getTripInfo."""

    code: int | str
    data: dict[str, Any] | None = None

    @property
    def trip(self) -> TripInfoTrip | None:
        """Return parsed trip object if present."""
        raw = self.data.get("trip") if self.data else None
        if raw is None:
            return None
        return TripInfoTrip.model_validate(raw)

    @property
    def flash_list(self) -> list[FlashRecord]:
        """Return parsed flash records if present."""
        raw = self.data.get("flash") if self.data else None
        if not isinstance(raw, list):
            return []
        return [FlashRecord.model_validate(item) for item in raw]


class WeatherReal(BaseModel):
    """Real-time weather data."""

    tmp: float
    ws: float
    hum: float


class WeatherData(BaseModel):
    """Weather payload from getWeather."""

    real: WeatherReal | None = None


class WeatherResponse(BaseModel):
    """Response wrapper for getWeather."""

    code: int | str
    data: WeatherData | None = None


class Waveform(BaseModel):
    """A single waveform from getTripRipple."""

    wave_type: str = Field(alias="waveType")
    items: list[dict[str, float]]


class TripRippleResponse(BaseModel):
    """Response wrapper for getTripRipple."""

    code: int | str
    data: dict[str, Waveform] | None = None

    @property
    def waveforms(self) -> list[Waveform]:
        """Return waveforms in insertion order."""
        if self.data is None:
            return []
        return list(self.data.values())


class ModuleResult(BaseModel):
    """Result of a single diagnostic module."""

    title: str
    markdown: str
    support_score: float
    weight: float
    contribution: float
    conclusion: str
    error: str | None = None


class DiagnosisReport(BaseModel):
    """Complete diagnosis report."""

    markdown: str
    images: list[bytes]
    total_confidence: float
    final_conclusion: str
    module_results: list[ModuleResult]
