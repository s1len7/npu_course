# 택배 감시 CCTV (현재 범위: 사람 방문 인식)

Raspberry Pi 5 + AI HAT+(Hailo-8L) 현관 카메라로 사람의 방문을 인식하고 역할(가족·택배기사 추정·미확인)과 의심 행동을 판정해 Home Assistant로 알린다.
에이전트 지침은 `AGENTS.md`, 설계는 `docs/`, 판정 규칙은 `skills/parcel-event-analysis/SKILL.md` 참고.

## 구성

| 경로 | 내용 |
| --- | --- |
| `docker/frigate/` | Frigate(HailoRT 4.23 교체 이미지) + MediaMTX(CSI 카메라 → RTSP) |
| `parcel_event_engine/` | Event Engine (Python) |
| `tests/` | 실제 카메라 없이 돌리는 replay 테스트 |

## Python 가상환경 (venv)

Event Engine은 `project/.venv`를 쓴다. 시스템 Python(3.13)에는 패키지를 설치하지 않는다.
`.venv/`는 git에 올리지 않으므로 새 장비에서는 아래 "처음 만들기"부터 한다.

### 처음 만들기

```bash
cd ~/silent_npu/project
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### 활성화 (activate)

```bash
cd ~/silent_npu/project
source .venv/bin/activate
```

- 활성화되면 프롬프트 앞에 `(.venv)`가 붙는다.
- 이후 `python`, `pip`은 venv 안의 것을 가리킨다. 확인: `which python` → `.../project/.venv/bin/python`

### 비활성화 (deactivate)

```bash
deactivate
```

- 프롬프트의 `(.venv)`가 사라지고 시스템 Python으로 돌아간다.

### 활성화 없이 실행

스크립트나 서비스에서는 activate 대신 venv의 python을 직접 쓴다.

```bash
.venv/bin/python -m parcel_event_engine.main
```

### 패키지 추가·변경

```bash
source .venv/bin/activate
pip install <패키지>==<버전>
pip freeze | grep -i <패키지>   # 설치된 버전 확인 후 requirements.txt에 고정 버전으로 추가
deactivate
```

- 패키지 추가는 설계 결정이므로 먼저 확인받는다(`AGENTS.md`).

### 다시 만들기

venv가 깨졌거나 Python 버전이 바뀌면 지우고 다시 만든다(재생성 가능한 산출물).

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Event Engine 실행

### 테스트

```bash
python3 -m unittest discover -s tests -t .           # 표준 라이브러리만 필요 (venv 없이도 됨)
.venv/bin/python -m unittest discover -s tests -t .  # venv로 실행
```

### replay (기록된 메시지 재생)

```bash
python3 -m parcel_event_engine.replay.event_replay tests/fixtures/household_arrival.jsonl
```

### 서비스 (MQTT 연결)

```bash
cp engine.env.example engine.env   # 처음 한 번, 값 채우기 (engine.env는 git 제외)
set -a; . ./engine.env; set +a     # 환경변수로 불러오기
.venv/bin/python -m parcel_event_engine.main
```

- 종료: `Ctrl+C`
- 구독: `frigate/events`, `frigate/available`, `<HA_STATESTREAM_TOPIC>/person/+/state`
- 발행: `parcel_engine/events` (판정 이벤트), `parcel_engine/available` (online/offline)
- broker에 연결되지 않으면 재시도하며 로그에 `MQTT connection ... failed, retrying`이 남는다.
