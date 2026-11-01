"""SKILL.md "필수 replay 테스트 (현재 범위)" 10개 시나리오."""

import json
import unittest
from datetime import timedelta
from pathlib import Path

from parcel_event_engine.engine import Engine
from parcel_event_engine.replay.event_replay import replay
from tests.helpers import DAY, KST, NIGHT, presence, run, track, types

FIXTURES = Path(__file__).parent / "fixtures"


class VisitScenarioTest(unittest.TestCase):
    def test_01_household_arrival(self):
        events = run(track("a", DAY, 0, 30, ["porch", "door"]), [presence("dad", "home", DAY, 20)])
        self.assertEqual(types(events), ["household_arrival"])
        self.assertEqual(events[0].certainty, "confirmed")

    def test_02_household_departure(self):
        events = run(track("a", DAY, 0, 30, ["door", "porch"]), [presence("dad", "not_home", DAY, 60)])
        self.assertEqual(types(events), ["household_departure"])
        self.assertEqual(events[0].certainty, "confirmed")

    def test_03_courier_short_visit(self):
        events = run(track("a", DAY, 0, 40, ["porch", "door", "porch"]))
        self.assertEqual(types(events), ["courier_visit_likely"])
        self.assertEqual(events[0].certainty, "probable")

    def test_04_unknown_short_pass(self):
        events = run(track("a", DAY, 0, 8, ["porch"], step=4))
        self.assertEqual(types(events), ["unknown_visitor"])

    def test_05_loitering_alerts_before_visit_ends(self):
        engine = Engine()
        msgs = track("a", DAY, 0, 240, ["porch"])
        live = []
        for at, payload in msgs:
            live += [(at, e) for e in engine.handle_frigate(payload)]
        self.assertEqual([e.event_type for _, e in live], ["suspicious_behavior"])
        self.assertLess(live[0][0], DAY + timedelta(seconds=240))
        self.assertEqual(live[0][1].suspicious_reasons, ("loitering",))
        closed = engine.tick(DAY + timedelta(days=1))
        self.assertEqual(types(closed), ["unknown_visitor"])  # 의심 알림은 한 번만

    def test_06_night_visit(self):
        events = run(track("a", NIGHT, 0, 20, ["porch"]))
        self.assertEqual(types(events), ["unknown_visitor", "suspicious_behavior"])
        self.assertIn("night_visit", events[1].suspicious_reasons)

    def test_07_repeated_visits_while_away(self):
        away = DAY - timedelta(hours=1)
        events = run(
            [presence("dad", "not_home", away, 0)],
            track("a", DAY, 0, 8, ["porch"], step=4),
            track("b", DAY, 600, 608, ["porch"], step=4),
            track("c", DAY, 1200, 1208, ["porch"], step=4),
        )
        suspicious = [e for e in events if e.event_type == "suspicious_behavior"]
        self.assertEqual(len(suspicious), 3)
        self.assertTrue(all("household_away" in e.suspicious_reasons for e in suspicious))
        self.assertIn("repeated_visits", suspicious[2].suspicious_reasons)
        self.assertNotIn("repeated_visits", suspicious[0].suspicious_reasons)

    def test_08_track_id_change_keeps_same_visit(self):
        events = run(track("a", DAY, 0, 20, ["porch"]), track("b", DAY, 25, 40, ["porch"]))
        self.assertEqual(len(events), 1)
        self.assertEqual(set(events[0].visit.tracks), {"a", "b"})
        self.assertEqual(events[0].visit.max_person_count, 1)

    def test_09_household_and_visitor_together(self):
        # 현재는 카메라당 방문 하나로 묶는다 (SKILL.md 방문 정의)
        events = run(
            track("a", DAY, 0, 30, ["porch", "door"]),
            track("b", DAY, 5, 25, ["porch"]),
            [presence("mom", "home", DAY, 10)],
        )
        self.assertEqual(types(events), ["household_arrival"])
        self.assertEqual(events[0].visit.max_person_count, 2)

    def test_10a_duplicate_messages_are_idempotent(self):
        groups = (track("a", DAY, 0, 30, ["porch", "door"]), [presence("dad", "home", DAY, 20)])
        once = [e.to_dict(KST) for e in run(*groups)]
        twice = [e.to_dict(KST) for e in run(*groups, duplicate=True)]
        self.assertEqual(once, twice)

    def test_10b_frigate_restart_closes_visit_without_end(self):
        engine = Engine()
        for _, payload in track("a", DAY, 0, 30, ["porch"], ended=False):
            engine.handle_frigate(payload)
        restarted = engine.handle_frigate_available("offline", DAY + timedelta(seconds=35))
        self.assertEqual(restarted, [])
        closed = engine.tick(DAY + timedelta(seconds=300))
        self.assertEqual(types(closed), ["unknown_visitor"])  # 오래 머묾 오탐 없음

    def test_10c_stale_track_fallback(self):
        # available 신호도 없으면 가만히 서 있는 사람과 구분할 수 없다 → 오래 머묾 알림 후 stale로 닫힘
        engine = Engine()
        for _, payload in track("a", DAY, 0, 30, ["porch"], ended=False):
            engine.handle_frigate(payload)
        self.assertEqual(types(engine.tick(DAY + timedelta(seconds=300))), ["suspicious_behavior"])
        stale = engine.tick(DAY + timedelta(seconds=30 + engine.config.stale_track_seconds))
        self.assertEqual(types(stale), ["unknown_visitor"])

    def test_replay_fixture(self):
        lines = (FIXTURES / "household_arrival.jsonl").read_text(encoding="utf-8").splitlines()
        events = replay(lines)
        self.assertEqual(types(events), ["household_arrival"])
        payload = events[0].to_dict(KST)
        json.dumps(payload)  # MQTT로 보낼 수 있는 형식인지
        self.assertEqual(payload["person_role"], "household")


class AdapterTest(unittest.TestCase):
    def test_invalid_and_false_positive_payloads_are_ignored(self):
        engine = Engine()
        self.assertEqual(engine.handle_frigate("not json"), [])
        self.assertEqual(engine.handle_frigate({"type": "new"}), [])
        _, payload = track("a", DAY, 0, 10, ["porch"])[0]
        payload["after"]["false_positive"] = True
        self.assertEqual(engine.handle_frigate(payload), [])
        self.assertIsNone(engine.now)


if __name__ == "__main__":
    unittest.main()
