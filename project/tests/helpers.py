"""테스트용 Frigate 메시지·재실 정보 생성 도우미."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from parcel_event_engine.domain.observations import PresenceChange
from parcel_event_engine.engine import Engine

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2026, 11, 1, 14, 0, tzinfo=KST)
NIGHT = datetime(2026, 11, 1, 23, 0, tzinfo=KST)


def track(track_id: str, base: datetime, start: float, end: float, path: list[str],
          step: float = 10.0, ended: bool = True) -> list[tuple[datetime, dict]]:
    """한 사람의 Frigate 메시지 묶음. path는 시간 순서대로 지나간 zone(반복 허용)."""
    start_ts = (base + timedelta(seconds=start)).timestamp()
    end_ts = (base + timedelta(seconds=end)).timestamp()
    times = [start]
    t = start + step
    while t < end:
        times.append(t)
        t += step
    times.append(end)

    messages = []
    entered: list[str] = []
    for i, t in enumerate(times):
        progress = (t - start) / (end - start) if end > start else 1.0
        zone = path[min(int(progress * len(path)), len(path) - 1)]
        if zone not in entered:
            entered.append(zone)
        last = i == len(times) - 1
        phase = "new" if i == 0 else ("end" if last and ended else "update")
        at = base + timedelta(seconds=t)
        messages.append((at, {
            "type": phase,
            "before": {},
            "after": {
                "id": track_id, "camera": "classroom", "label": "person",
                "frame_time": at.timestamp(), "start_time": start_ts,
                "end_time": end_ts if phase == "end" else None,
                "entered_zones": list(entered), "current_zones": [zone],
                "score": 0.8, "top_score": 0.8, "has_snapshot": True, "false_positive": False,
            },
        }))
    return messages


def presence(person: str, state: str, base: datetime, at: float) -> tuple[datetime, PresenceChange]:
    when = base + timedelta(seconds=at)
    return when, PresenceChange(person, state, when)


def run(*groups: list, engine: Engine | None = None, duplicate: bool = False) -> list:
    """시간순으로 섞어 엔진에 넣고, 마지막에 열린 방문을 닫는다."""
    engine = engine or Engine()
    items = sorted((x for g in groups for x in g), key=lambda x: x[0])
    events = []
    for _, item in items:
        for _ in range(2 if duplicate else 1):
            if isinstance(item, PresenceChange):
                events += engine.handle_presence(item)
            else:
                events += engine.handle_frigate(item)
    events += engine.tick(items[-1][0] + timedelta(days=1))
    return events


def types(events: list) -> list[str]:
    return [e.event_type for e in events]
