"""paho-mqtt 연결: 구독 → MessageRouter → 이벤트 발행."""

import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from parcel_event_engine.domain.event_rules import EngineEvent
from parcel_event_engine.messaging.router import MessageRouter
from parcel_event_engine.messaging.settings import MqttSettings

logger = logging.getLogger(__name__)


class MqttBridge:
    def __init__(self, settings: MqttSettings, router: MessageRouter) -> None:
        self._settings = settings
        self._router = router
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=settings.client_id, clean_session=False,
        )
        if settings.username:
            self._client.username_pw_set(settings.username, settings.password)
        # 엔진이 비정상 종료되면 broker가 offline을 대신 발행한다
        self._client.will_set(settings.availability_topic, "offline", qos=1, retain=True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self._on_connect
        self._client.on_connect_fail = self._on_connect_fail
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def start(self) -> None:
        s = self._settings
        logger.info(f"Connecting to MQTT broker {s.host}:{s.port}")
        # 첫 연결이 실패해도 loop가 계속 재시도한다
        self._client.connect_async(s.host, s.port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.publish(self._settings.availability_topic, "offline", qos=1, retain=True)
        self._client.disconnect()
        self._client.loop_stop()

    def tick(self) -> None:
        self.publish(self._router.tick(datetime.now(timezone.utc)))

    def publish(self, events: list[EngineEvent]) -> None:
        for event in events:
            info = self._client.publish(
                self._settings.events_topic, self._router.encode(event), qos=1,
            )
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Publish failed: rc={info.rc} event_id={event.event_id}")

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.error(f"MQTT connection refused: {reason_code}")
            return
        logger.info("MQTT connected")
        client.publish(self._settings.availability_topic, "online", qos=1, retain=True)
        for topic in self._settings.subscriptions:
            client.subscribe(topic, qos=1)
            logger.info(f"Subscribed: {topic}")

    def _on_connect_fail(self, client, userdata) -> None:
        s = self._settings
        logger.warning(f"MQTT connection to {s.host}:{s.port} failed, retrying")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            logger.warning(f"MQTT disconnected unexpectedly: {reason_code}, retrying")

    def _on_message(self, client, userdata, message) -> None:
        try:
            events = self._router.handle(message.topic, message.payload, datetime.now(timezone.utc))
            self.publish(events)
        except Exception:
            # 메시지 하나 때문에 네트워크 스레드가 죽지 않도록 한다
            logger.exception(f"Failed to handle message on {message.topic}")
