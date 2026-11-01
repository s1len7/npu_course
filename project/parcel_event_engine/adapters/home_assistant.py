"""HA 재실 정보 → PresenceChange.

HA의 MQTT Statestream 통합이 발행하는 `<base_topic>/person/<이름>/state` 토픽을 받는다.
payload는 상태 문자열(home, not_home, 또는 zone 이름)이다.
https://www.home-assistant.io/integrations/mqtt_statestream/
"""

import logging
from datetime import datetime

from parcel_event_engine.domain.observations import PresenceChange

logger = logging.getLogger(__name__)


def parse_presence(base_topic: str, topic: str, payload: bytes | str, at: datetime) -> PresenceChange | None:
    prefix = f"{base_topic.rstrip('/')}/person/"
    if not topic.startswith(prefix) or not topic.endswith("/state"):
        return None
    person = topic[len(prefix):-len("/state")]
    if not person or "/" in person:
        return None
    state = (payload.decode("utf-8", "replace") if isinstance(payload, bytes) else payload).strip().strip('"')
    if state in ("unknown", "unavailable", ""):
        logger.info(f"Ignoring presence without a usable state: person={person} state={state!r}")
        return None
    # home 외의 zone(회사 등)은 집에 없는 것으로 본다
    return PresenceChange(person, "home" if state == "home" else "not_home", at)
