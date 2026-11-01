"""MQTT 토픽 → 엔진 입력 분배. 네트워크 라이브러리에 의존하지 않는다(테스트 가능)."""

import json
import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from parcel_event_engine.adapters.home_assistant import parse_presence
from parcel_event_engine.domain.event_rules import EngineEvent
from parcel_event_engine.engine import Engine
from parcel_event_engine.messaging.settings import MqttSettings

logger = logging.getLogger(__name__)


class MessageRouter:
    def __init__(self, engine: Engine, settings: MqttSettings) -> None:
        self._engine = engine
        self._settings = settings
        self._tz = ZoneInfo(engine.config.timezone)
        # paho 네트워크 스레드(메시지)와 메인 스레드(tick)가 엔진을 함께 쓰므로 잠근다
        self._lock = threading.Lock()

    def handle(self, topic: str, payload: bytes, now: datetime) -> list[EngineEvent]:
        s = self._settings
        with self._lock:
            if topic == f"{s.frigate_topic}/events":
                return self._engine.handle_frigate(payload)
            if topic == f"{s.frigate_topic}/available":
                state = payload.decode("utf-8", "replace").strip()
                return self._engine.handle_frigate_available(state, now)
            change = parse_presence(s.ha_statestream_topic, topic, payload, now)
            if change:
                return self._engine.handle_presence(change)
        logger.debug(f"Ignoring message on topic {topic}")
        return []

    def tick(self, now: datetime) -> list[EngineEvent]:
        with self._lock:
            return self._engine.tick(now)

    def encode(self, event: EngineEvent) -> str:
        return json.dumps(event.to_dict(self._tz), ensure_ascii=False)
