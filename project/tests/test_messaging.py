"""MQTT 토픽 분배·HA 재실 정보·설정 테스트 (paho 없이 실행)."""

import json
import unittest
from datetime import timedelta

from parcel_event_engine.adapters.home_assistant import parse_presence
from parcel_event_engine.engine import Engine
from parcel_event_engine.messaging.router import MessageRouter
from parcel_event_engine.messaging.settings import MqttSettings
from tests.helpers import DAY, track

BASE = "homeassistant/statestream"


class PresenceAdapterTest(unittest.TestCase):
    def test_states(self):
        topic = f"{BASE}/person/dad/state"
        self.assertEqual(parse_presence(BASE, topic, b"home", DAY).state, "home")
        self.assertEqual(parse_presence(BASE, topic, b"not_home", DAY).state, "not_home")
        self.assertEqual(parse_presence(BASE, topic, b"work", DAY).state, "not_home")
        self.assertEqual(parse_presence(BASE, topic, b'"home"', DAY).person, "dad")

    def test_ignored(self):
        self.assertIsNone(parse_presence(BASE, f"{BASE}/person/dad/state", b"unavailable", DAY))
        self.assertIsNone(parse_presence(BASE, f"{BASE}/person/dad/friendly_name", b"Dad", DAY))
        self.assertIsNone(parse_presence(BASE, f"{BASE}/light/porch/state", b"on", DAY))


class SettingsTest(unittest.TestCase):
    def test_from_env(self):
        s = MqttSettings.from_env({"ENGINE_MQTT_HOST": "silent-nas-ts", "ENGINE_MQTT_USER": "engine"})
        self.assertEqual((s.host, s.port, s.username, s.password), ("silent-nas-ts", 1883, "engine", None))
        self.assertIn("frigate/events", s.subscriptions)
        self.assertEqual(s.events_topic, "parcel_engine/events")

    def test_invalid_port(self):
        with self.assertRaises(ValueError):
            MqttSettings.from_env({"ENGINE_MQTT_PORT": "abc"})


class RouterTest(unittest.TestCase):
    def test_routes_frigate_and_presence_to_events(self):
        router = MessageRouter(Engine(), MqttSettings())
        events = router.handle(f"{BASE}/person/dad/state", b"home", DAY + timedelta(seconds=20))
        for at, payload in track("a", DAY, 0, 30, ["porch", "door"]):
            events += router.handle("frigate/events", json.dumps(payload).encode(), at)
        events += router.tick(DAY + timedelta(minutes=5))
        self.assertEqual([e.event_type for e in events], ["household_arrival"])
        self.assertEqual(json.loads(router.encode(events[0]))["person_role"], "household")

    def test_frigate_available_and_unknown_topic(self):
        router = MessageRouter(Engine(), MqttSettings())
        self.assertEqual(router.handle("frigate/available", b"online", DAY), [])
        self.assertEqual(router.handle("other/topic", b"x", DAY), [])


if __name__ == "__main__":
    unittest.main()
