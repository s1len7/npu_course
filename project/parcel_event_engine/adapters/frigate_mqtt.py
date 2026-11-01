"""Frigate `frigate/events` MQTT payload → Observation 변환.

Frigate 버전별 형식 차이는 이 모듈에서만 흡수한다.
형식: https://docs.frigate.video/integrations/mqtt
"""

import json
import logging
from datetime import datetime, timezone

from parcel_event_engine.domain.observations import Observation

logger = logging.getLogger(__name__)

_PHASES = {"new", "update", "end"}


def _to_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return None


def parse_event(payload: dict | str | bytes) -> Observation | None:
    """잘못된 payload나 오탐(false_positive)은 None을 돌려준다."""
    try:
        data = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        phase = data["type"]
        after = data["after"]
        event_id = after["id"]
        camera = after["camera"]
        label = after["label"]
    except (json.JSONDecodeError, KeyError, TypeError) as err:
        logger.warning(f"Invalid Frigate event payload: {err!r}")
        return None

    if phase not in _PHASES:
        logger.warning(f"Unknown Frigate event type: {phase}")
        return None
    if after.get("false_positive"):
        return None

    observed_at = None
    if phase == "end":
        observed_at = _to_datetime(after.get("end_time"))
    observed_at = (
        observed_at
        or _to_datetime(after.get("frame_time"))
        or _to_datetime(after.get("start_time"))
    )
    if observed_at is None:
        logger.warning(f"Frigate event without timestamp: id={event_id}")
        return None

    zones: list[str] = []
    for zone in [*after.get("entered_zones", []), *after.get("current_zones", [])]:
        if zone not in zones:
            zones.append(zone)

    return Observation(
        frigate_event_id=event_id,
        camera=camera,
        label=label,
        phase=phase,
        observed_at=observed_at,
        zones=tuple(zones),
        current_zones=tuple(after.get("current_zones", [])),
        score=float(after.get("top_score") or after.get("score") or 0.0),
        has_snapshot=bool(after.get("has_snapshot")),
    )
