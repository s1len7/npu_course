"""엔진 설정값."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineConfig:
    camera: str = "classroom"
    # Frigate zone 이름 (zone 설정 후 맞출 것)
    porch_zone: str = "porch"
    door_zone: str = "door"
    timezone: str = "Asia/Seoul"

    # 아래 기준값은 임시값이다. 실측 후 조정한다 (IMPLEMENTATION_PLAN Phase 2)
    visit_grace_seconds: float = 10.0
    stale_track_seconds: float = 600.0
    min_observed_seconds: float = 2.0
    courier_max_dwell_seconds: float = 120.0
    loiter_seconds: float = 180.0
    night_start_hour: int = 22
    night_end_hour: int = 6
    presence_window_seconds: float = 300.0
    repeat_window_seconds: float = 1800.0
    repeat_visit_count: int = 3
