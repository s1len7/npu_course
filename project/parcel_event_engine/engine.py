"""엔진 본체: 입력(Frigate·재실 정보)을 받아 방문 이벤트를 만든다. 네트워크 I/O는 하지 않는다."""

import logging
from collections import OrderedDict
from datetime import datetime, timedelta

from parcel_event_engine.adapters.frigate_mqtt import parse_event
from parcel_event_engine.config import EngineConfig
from parcel_event_engine.domain.event_rules import EngineEvent, classify_visit, live_loitering
from parcel_event_engine.domain.observations import PresenceChange
from parcel_event_engine.domain.visits import VisitTracker

logger = logging.getLogger(__name__)

_DEDUPE_LIMIT = 10_000


class Engine:
    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()
        self._visits = VisitTracker(self.config)
        self._seen: OrderedDict[tuple, None] = OrderedDict()
        self._presence_changes: list[PresenceChange] = []
        self._presence_state: dict[str, str] = {}
        self._unknown_starts: list[datetime] = []
        self._now: datetime | None = None

    @property
    def now(self) -> datetime | None:
        return self._now

    def handle_frigate(self, payload: dict | str | bytes) -> list[EngineEvent]:
        obs = parse_event(payload)
        if obs is None or obs.label != "person" or obs.camera != self.config.camera:
            return []
        key = (obs.frigate_event_id, obs.phase, obs.observed_at, obs.zones)
        if key in self._seen:
            logger.debug(f"Duplicate Frigate message ignored: track={obs.frigate_event_id}")
            return []
        self._seen[key] = None
        if len(self._seen) > _DEDUPE_LIMIT:
            self._seen.popitem(last=False)
        # 이전 방문이 이미 끝났으면 먼저 닫고 나서 새 관측을 넣는다
        events = self.tick(obs.observed_at)
        self._visits.observe(obs)
        return events + self.tick(obs.observed_at)

    def handle_frigate_available(self, state: str, at: datetime) -> list[EngineEvent]:
        """`frigate/available` 토픽(online / offline). 재시작 시 진행 중 track을 정리한다."""
        if state in ("online", "offline"):
            logger.warning(f"Frigate availability changed: {state}, ending active tracks")
            self._visits.end_all_tracks()
        return self.tick(at)

    def handle_presence(self, change: PresenceChange) -> list[EngineEvent]:
        if change in self._presence_changes:
            return []
        self._presence_changes.append(change)
        self._presence_state[change.person] = change.state
        return self.tick(change.at)

    def tick(self, now: datetime) -> list[EngineEvent]:
        """시간을 진행시킨다. 시간은 뒤로 가지 않는다(늦게 도착한 메시지 대비)."""
        self._now = now if self._now is None else max(self._now, now)
        events: list[EngineEvent] = []
        # 끝난 방문을 먼저 닫아야, 이미 떠난 사람을 "오래 머묾"으로 판정하지 않는다
        for visit in self._visits.close_expired(self._now):
            anyone_home = (
                any(s == "home" for s in self._presence_state.values())
                if self._presence_state else None
            )
            closed = classify_visit(
                visit, self._presence_changes, anyone_home, self._unknown_starts, self.config,
            )
            if closed[0].person_role in ("unknown", "courier_likely"):
                self._unknown_starts.append(visit.started_at)
            events += closed
        for visit in self._visits.active_visits():
            event = live_loitering(visit, self._now, self.config)
            if event:
                events.append(event)
        self._prune()
        for event in events:
            logger.info(f"Event: {event.event_type} visit_id={event.visit.visit_id}")
        return events

    def _prune(self) -> None:
        keep = timedelta(seconds=max(self.config.repeat_window_seconds,
                                     self.config.presence_window_seconds) * 2)
        cutoff = self._now - keep
        self._presence_changes = [c for c in self._presence_changes if c.at >= cutoff]
        self._unknown_starts = [t for t in self._unknown_starts if t >= cutoff]
