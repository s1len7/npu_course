"""person 관측을 방문(visit) 단위로 묶는다.

Frigate track ID는 가림·재진입·재시작으로 바뀔 수 있으므로 방문과 동일시하지 않는다.
현재는 카메라당 진행 중인 방문을 하나로 묶는다(동시에 온 여러 사람도 같은 방문).
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from parcel_event_engine.config import EngineConfig
from parcel_event_engine.domain.observations import Observation

logger = logging.getLogger(__name__)


@dataclass
class Visit:
    visit_id: str
    camera: str
    started_at: datetime
    last_seen_at: datetime
    # track ID → 진행 중 여부
    tracks: dict[str, bool] = field(default_factory=dict)
    zones: list[str] = field(default_factory=list)
    # 진입·이탈 방향 판정용: 처음/마지막으로 관측된 zone (entered_zones는 순서 반복을 잃으므로 따로 기록)
    first_zone: str | None = None
    last_zone: str | None = None
    max_person_count: int = 0
    snapshot_event_id: str | None = None
    snapshot_score: float = 0.0
    ended_at: datetime | None = None
    suspicious_emitted: bool = False

    @property
    def dwell_seconds(self) -> float:
        end = self.ended_at or self.last_seen_at
        return (end - self.started_at).total_seconds()

    @property
    def active_count(self) -> int:
        return sum(self.tracks.values())


class VisitTracker:
    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._active: dict[str, Visit] = {}

    def active_visits(self) -> list[Visit]:
        return list(self._active.values())

    def observe(self, obs: Observation) -> Visit:
        visit = self._active.get(obs.camera)
        if visit is None:
            visit_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{obs.camera}/{obs.frigate_event_id}"))
            visit = Visit(visit_id, obs.camera, obs.observed_at, obs.observed_at)
            self._active[obs.camera] = visit
            logger.info(f"Visit started: visit_id={visit_id} track={obs.frigate_event_id}")

        visit.tracks[obs.frigate_event_id] = obs.phase != "end"
        visit.started_at = min(visit.started_at, obs.observed_at)
        if obs.current_zones:
            if visit.first_zone is None:
                visit.first_zone = obs.current_zones[0]
            if obs.observed_at >= visit.last_seen_at:
                visit.last_zone = obs.current_zones[0]
        visit.last_seen_at = max(visit.last_seen_at, obs.observed_at)
        for zone in obs.zones:
            if zone not in visit.zones:
                visit.zones.append(zone)
        visit.max_person_count = max(visit.max_person_count, visit.active_count)
        if obs.has_snapshot and obs.score >= visit.snapshot_score:
            visit.snapshot_event_id = obs.frigate_event_id
            visit.snapshot_score = obs.score
        return visit

    def end_all_tracks(self) -> None:
        """Frigate가 재시작되면 이전 track의 end 메시지는 오지 않으므로 모두 끝난 것으로 본다."""
        for visit in self._active.values():
            for track_id in visit.tracks:
                visit.tracks[track_id] = False

    def close_expired(self, now: datetime) -> list[Visit]:
        """끝난 방문을 닫아서 돌려준다.

        - 모든 track이 끝나고 grace 시간이 지나면 닫는다.
        - end 메시지가 오지 않은 track(Frigate 재시작 등)은 stale 시간이 지나면 닫는다.
        """
        closed = []
        for camera, visit in list(self._active.items()):
            idle = (now - visit.last_seen_at).total_seconds()
            ended = visit.active_count == 0 and idle >= self._config.visit_grace_seconds
            stale = idle >= self._config.stale_track_seconds
            if ended or stale:
                if stale and not ended:
                    logger.warning(f"Closing stale visit: visit_id={visit.visit_id}")
                visit.ended_at = visit.last_seen_at
                del self._active[camera]
                closed.append(visit)
                logger.info(
                    f"Visit closed: visit_id={visit.visit_id} dwell={visit.dwell_seconds:.1f}s"
                )
        return closed
