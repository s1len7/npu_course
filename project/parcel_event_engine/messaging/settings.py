"""MQTT 접속·토픽 설정. 값은 환경변수에서 읽는다 (예시: engine.env.example)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MqttSettings:
    host: str = "localhost"
    port: int = 1883
    username: str | None = None
    password: str | None = None
    client_id: str = "parcel-event-engine"
    frigate_topic: str = "frigate"
    ha_statestream_topic: str = "homeassistant/statestream"
    engine_topic: str = "parcel_engine"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "MqttSettings":
        env = os.environ if env is None else env
        port = env.get("ENGINE_MQTT_PORT", "1883")
        if not port.isdigit():
            raise ValueError(f"ENGINE_MQTT_PORT must be a number: {port!r}")
        return cls(
            host=env.get("ENGINE_MQTT_HOST", cls.host),
            port=int(port),
            username=env.get("ENGINE_MQTT_USER") or None,
            password=env.get("ENGINE_MQTT_PASSWORD") or None,
            client_id=env.get("ENGINE_MQTT_CLIENT_ID", cls.client_id),
            frigate_topic=env.get("FRIGATE_TOPIC_PREFIX", cls.frigate_topic),
            ha_statestream_topic=env.get("HA_STATESTREAM_TOPIC", cls.ha_statestream_topic),
            engine_topic=env.get("ENGINE_TOPIC_PREFIX", cls.engine_topic),
        )

    @property
    def subscriptions(self) -> list[str]:
        return [
            f"{self.frigate_topic}/events",
            f"{self.frigate_topic}/available",
            f"{self.ha_statestream_topic}/person/+/state",
        ]

    @property
    def events_topic(self) -> str:
        return f"{self.engine_topic}/events"

    @property
    def availability_topic(self) -> str:
        return f"{self.engine_topic}/available"
