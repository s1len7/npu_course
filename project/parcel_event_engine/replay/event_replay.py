"""JSONL fixture를 엔진에 재생하고 이벤트를 JSON 줄로 출력한다.

한 줄에 하나:
  {"kind": "frigate", "payload": {...frigate/events payload...}}
  {"kind": "presence", "person": "dad", "state": "home", "at": "2026-11-01T14:00:00+09:00"}
  {"kind": "frigate_available", "state": "offline", "at": "..."}
  {"kind": "tick", "at": "..."}

실행: python3 -m parcel_event_engine.replay.event_replay tests/fixtures/<파일>.jsonl
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from parcel_event_engine.domain.event_rules import EngineEvent
from parcel_event_engine.domain.observations import PresenceChange
from parcel_event_engine.engine import Engine

logger = logging.getLogger(__name__)


def replay(lines: list[str], engine: Engine | None = None) -> list[EngineEvent]:
    engine = engine or Engine()
    events: list[EngineEvent] = []
    last: datetime | None = None
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            kind = item["kind"]
            if kind == "frigate":
                events += engine.handle_frigate(item["payload"])
            elif kind == "presence":
                at = datetime.fromisoformat(item["at"])
                events += engine.handle_presence(PresenceChange(item["person"], item["state"], at))
                last = at
            elif kind == "frigate_available":
                at = datetime.fromisoformat(item["at"])
                events += engine.handle_frigate_available(item["state"], at)
                last = at
            elif kind == "tick":
                last = datetime.fromisoformat(item["at"])
                events += engine.tick(last)
            else:
                logger.warning(f"Line {number}: unknown kind {kind}")
        except (json.JSONDecodeError, KeyError, ValueError) as err:
            logger.warning(f"Line {number}: skipped ({err!r})")
    # 끝에서 열린 방문을 모두 닫는다
    times = [t for t in (engine.now, last) if t]
    if times:
        events += engine.tick(max(times) + timedelta(days=1))
    return events


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(message)s")
    if len(argv) != 2:
        print("usage: python3 -m parcel_event_engine.replay.event_replay <fixture.jsonl>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"fixture not found: {path}", file=sys.stderr)
        return 1
    engine = Engine()
    tz = ZoneInfo(engine.config.timezone)
    for event in replay(path.read_text(encoding="utf-8").splitlines(), engine):
        print(json.dumps(event.to_dict(tz), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
