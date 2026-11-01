"""방문 → 역할 추정·의심 행동 판정 (규칙: skills/parcel-event-analysis/SKILL.md)."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from parcel_event_engine.config import EngineConfig
from parcel_event_engine.domain.observations import PresenceChange
from parcel_event_engine.domain.visits import Visit

# certainty → role_confidence. 임시값, 실측 후 조정
_CONFIDENCE = {"confirmed": 0.9, "probable": 0.6, "uncertain": 0.3}


@dataclass(frozen=True)
class EngineEvent:
    event_type: str
    visit: Visit
    person_role: str
    certainty: str
    evidence: tuple[str, ...]
    suspicious_reasons: tuple[str, ...] = field(default=())

    @property
    def event_id(self) -> str:
        # 같은 방문·같은 종류는 같은 ID → 재처리해도 중복 알림 없음
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.visit.visit_id}/{self.event_type}"))

    def to_dict(self, tz: ZoneInfo) -> dict:
        v = self.visit
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": (v.ended_at or v.last_seen_at).astimezone(tz).isoformat(),
            "camera": v.camera,
            "visit_id": v.visit_id,
            "started_at": v.started_at.astimezone(tz).isoformat(),
            "dwell_seconds": round(v.dwell_seconds, 1),
            "zones": list(v.zones),
            "person_count": v.max_person_count,
            "person_track_ids": list(v.tracks),
            "person_role": self.person_role,
            "role_confidence": _CONFIDENCE[self.certainty],
            "certainty": self.certainty,
            "suspicious_reasons": list(self.suspicious_reasons),
            "frigate_event_id": v.snapshot_event_id,
            "evidence": list(self.evidence),
        }


def _within(changes: list[PresenceChange], state: str, visit: Visit, window: float) -> list[PresenceChange]:
    lo = visit.started_at - timedelta(seconds=window)
    hi = (visit.ended_at or visit.last_seen_at) + timedelta(seconds=window)
    return [c for c in changes if c.state == state and lo <= c.at <= hi]


def is_night(at: datetime, config: EngineConfig) -> bool:
    hour = at.astimezone(ZoneInfo(config.timezone)).hour
    if config.night_start_hour > config.night_end_hour:
        return hour >= config.night_start_hour or hour < config.night_end_hour
    return config.night_start_hour <= hour < config.night_end_hour


def live_loitering(visit: Visit, now: datetime, config: EngineConfig) -> EngineEvent | None:
    """진행 중인 방문이 기준 시간 이상 이어지면 끝나기 전에 한 번 알린다."""
    # 진행 중인 track이 있을 때만 (모두 떠나고 grace 대기 중인 방문은 제외)
    if visit.suspicious_emitted or visit.active_count == 0 or config.door_zone in visit.zones:
        return None
    if (now - visit.started_at).total_seconds() < config.loiter_seconds:
        return None
    visit.suspicious_emitted = True
    return EngineEvent(
        "suspicious_behavior", visit, "unknown", "probable",
        (f"stayed over {config.loiter_seconds:.0f}s without entering",),
        ("loitering",),
    )


def classify_visit(
    visit: Visit,
    presence_changes: list[PresenceChange],
    anyone_home: bool | None,
    recent_unknown_starts: list[datetime],
    config: EngineConfig,
) -> list[EngineEvent]:
    """닫힌 방문 하나에 대한 이벤트 목록 (역할 이벤트 + 필요하면 의심 행동)."""
    zones = visit.zones
    door = config.door_zone
    dwell = visit.dwell_seconds
    window = config.presence_window_seconds
    entering = visit.last_zone == door
    leaving = visit.first_zone == door and not entering
    arrivals = _within(presence_changes, "home", visit, window)
    departures = _within(presence_changes, "not_home", visit, window)
    night = is_night(visit.started_at, config)

    evidence: list[str] = [f"dwell {dwell:.1f}s", f"zones {zones}"]
    if dwell < config.min_observed_seconds:
        role, event_type, certainty = "unclassified", "visit_uncertain", "uncertain"
        evidence.append("observed too briefly")
    elif entering or arrivals:
        role, event_type = "household", "household_arrival"
        certainty = "confirmed" if entering and arrivals else "probable"
        if entering:
            evidence.append("ended at door zone")
        evidence += [f"presence home: {c.person}" for c in arrivals]
    elif leaving or departures:
        role, event_type = "household", "household_departure"
        certainty = "confirmed" if leaving and departures else "probable"
        if leaving:
            evidence.append("started at door zone")
        evidence += [f"presence not_home: {c.person}" for c in departures]
    elif door in zones and dwell <= config.courier_max_dwell_seconds and not night:
        role, event_type, certainty = "courier_likely", "courier_visit_likely", "probable"
        evidence.append("short daytime visit to door without entering")
    else:
        role, event_type, certainty = "unknown", "unknown_visitor", "probable"

    events = [EngineEvent(event_type, visit, role, certainty, tuple(evidence))]

    if role == "household" or visit.suspicious_emitted:
        return events
    reasons: list[str] = []
    if dwell >= config.loiter_seconds:
        reasons.append("loitering")
    if night:
        reasons.append("night_visit")
    if anyone_home is False:
        reasons.append("household_away")
    lo = visit.started_at - timedelta(seconds=config.repeat_window_seconds)
    repeats = [t for t in recent_unknown_starts if lo <= t < visit.started_at]
    if len(repeats) + 1 >= config.repeat_visit_count:
        reasons.append("repeated_visits")
    if reasons:
        visit.suspicious_emitted = True
        events.append(EngineEvent(
            "suspicious_behavior", visit, role, "probable", tuple(evidence), tuple(reasons),
        ))
    return events
