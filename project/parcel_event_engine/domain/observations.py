"""엔진 내부 표준 관측값. Frigate·HA 원본 형식에 의존하지 않는다."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Observation:
    frigate_event_id: str
    camera: str
    label: str
    phase: str  # new / update / end
    observed_at: datetime
    zones: tuple[str, ...]  # 진입 순서대로 누적된 zone (중복 없음)
    current_zones: tuple[str, ...]  # 이 관측 시점에 있는 zone
    score: float
    has_snapshot: bool


@dataclass(frozen=True)
class PresenceChange:
    person: str
    state: str  # home / not_home
    at: datetime
