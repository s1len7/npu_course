"""서비스 실행: python -m parcel_event_engine.main (venv 필요, README 참고)."""

import logging
import signal
import sys
import threading

from parcel_event_engine.engine import Engine
from parcel_event_engine.messaging.mqtt_client import MqttBridge
from parcel_event_engine.messaging.router import MessageRouter
from parcel_event_engine.messaging.settings import MqttSettings

TICK_SECONDS = 1.0

logger = logging.getLogger("parcel_event_engine")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = MqttSettings.from_env()
    except ValueError as err:
        logger.error(f"Invalid settings: {err}")
        return 2

    bridge = MqttBridge(settings, MessageRouter(Engine(), settings))
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    bridge.start()
    try:
        # 메시지가 없어도 시간이 흘러야 방문이 닫히고 오래 머묾이 판정된다
        while not stop.wait(TICK_SECONDS):
            bridge.tick()
    finally:
        logger.info("Shutting down")
        bridge.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
