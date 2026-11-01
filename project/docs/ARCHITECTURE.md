# 아키텍처 및 재사용 검토

## 1. 권장 구성

```text
[현관 RTSP Camera]
        |
        v
[Raspberry Pi 5 + AI HAT 13 TOPS]
  ├─ Frigate NVR
  │   ├─ RTSP ingest
  │   ├─ Hailo object detector
  │   ├─ object tracking / zones
  │   ├─ snapshots / recordings
  │   └─ MQTT events
  │
  └─ Parcel Event Engine (Python)
      ├─ Frigate adapter
      ├─ observation normalizer
      ├─ parcel identity / lifecycle
      ├─ person role evidence
      ├─ event state machine
      ├─ SQLite
      └─ MQTT publisher
                 |
                 v
       [공용 MQTT Broker]
                 |
                 v
      [기존 Home Assistant 장비]
        ├─ Frigate integration
        ├─ automations
        └─ mobile notifications
```

## 2. 기존 구성요소 재사용 여부

| 기능 | 재사용 대상 | 직접 구현 필요 |
|---|---|---|
| 카메라 RTSP 수신 | Frigate | 거의 없음 |
| 사람 객체 검출 | Frigate + Hailo 기본 모델 | 카메라 환경별 threshold 조정 |
| 객체 tracking | Frigate | parcel identity 보완 로직만 |
| 영역 구분 | Frigate zones | 현관 영상에 맞춘 zone 설정 |
| 스냅샷 | Frigate | 이벤트별 snapshot 연결 |
| 짧은 녹화/clip | Frigate recordings/API | 이벤트와 clip 연결하는 adapter |
| 택배 상자 검출 | 검증된 package model 탐색 | 모델이 없거나 성능 부족 시 데이터 수집/학습/변환 |
| 가족/택배기사 구분 | 완전한 범용 기성 기능 없음 | evidence fusion 및 필요 시 수동 설정 |
| 택배별 상태 | 범용 NVR 기능이 아님 | Parcel Event Engine |
| 정상/비정상 행동 판정 | 기존 사례의 간단한 규칙 참고 | 사용자 시나리오에 맞는 상태 머신 |
| HA 알림 | MQTT + HA automation | topic/payload/automation 구성 |

## 3. Hailo 및 Frigate

이 장비의 NPU는 Hailo-8L로 확인됐다(`../../AGENTS.md`). Frigate 공식 문서는 Hailo-8L detector를 지원하고 기본 모델로 YOLOv6n을 안내하므로, Frigate 기본 사람 검출부터 검증하는 것이 가장 낮은 위험의 출발점이다.

일반 객체 모델의 label set에 전용 `parcel` 클래스가 있다고 가정하지 않는다. 택배 검출은 실제 현관 영상에서 별도로 검증한다.

호스트에는 교육용 `hailo-all` 5.1.1(HailoRT 4.23.0)이 이미 설치돼 있다. Frigate 컨테이너가 요구하는 드라이버 버전과 맞는지는 **미확인**이며, Frigate 설치 문서의 Trixie 안내를 확인한 뒤 결정한다.

공식 문서:
- https://docs.frigate.video/configuration/object_detectors/
- https://docs.frigate.video/frigate/installation/

## 4. 유사 오픈소스 사례

### Sixfab Porch Pirate / Frigate Package Detection
https://docs.sixfab.com/docs/frigate-package-detection-raspberry-pi-5-deepx

Frigate MQTT event를 Python listener가 구독하고 package/person track 이벤트를 조합해 의심스러운 제거를 판정하는 접근은 본 프로젝트에 매우 가깝다. 다만 해당 가이드는 DEEPX DX-M1M 하드웨어를 대상으로 하므로 Hailo 13 TOPS에서 그대로 실행되는 패키지/모델/설정으로 취급하지 않는다. 이벤트 처리 구조와 실패 사례를 참고한다.

해당 예제의 단순한 "처음 놓은 사람 track ID와 다른 사람이 나타나고 package event가 종료되면 경보" 방식은 tracker ID 변경, 재진입, 가림, event 종료 이유를 충분히 처리하지 못할 수 있다. 본 프로젝트는 parcel lifecycle, certainty, occlusion grace period, idempotency를 추가한다.

### DeliveryProtect
https://github.com/kuscholar/DeliveryProtect

배송 및 제거 이벤트와 사진 증거를 제공하는 Raspberry Pi 기반 prototype이다. 센서 기반 접근이므로 영상 기반 객체/행동 인식의 직접 대체재는 아니지만, 이벤트와 사진 증거를 분리해 설계하는 참고 사례다.

### Frigate
https://docs.frigate.video/

NVR, detector, tracker, zones, MQTT, snapshot/recording 기능을 맡긴다. 직접 구현 범위를 크게 줄이는 핵심 구성요소다.

## 5. 모델 전략

> 현재는 1단계(기본 모델로 사람 검출)만 진행한다. 2·3단계(택배 검출)는 보류이며 조사 결과는 `IMPLEMENTATION_PLAN.md`의 택배 검출 TODO에 있다.

### 1단계: 기본 Hailo 모델
- Frigate 기본 Hailo-8L YOLOv6n을 사용
- 사람 검출, tracking, zone 통과부터 검증
- package label이 기본 모델에 없을 수 있음을 전제로 한다.

### 2단계: 공개 package detection 모델 탐색
- Hailo Model Zoo 및 공개 GitHub/Hugging Face 모델 조사
- 라이선스, 학습 데이터, label definition, input size, NMS/post-process, Hailo HEF 제공 여부 확인
- 모델이 있다고 해서 Frigate에서 바로 쓸 수 있다고 가정하지 않는다.

### 3단계: 필요할 때만 직접 데이터 준비
공개 모델이 실제 카메라 각도에서 충분하지 않을 경우에만:
- 낮/밤/역광/비/복수 박스 등 대표 영상 수집
- parcel bounding box annotation
- 기존 모델 fine-tuning 또는 detector 학습 검토
- Hailo 호환 HEF 변환/컴파일
- Frigate custom model 설정
- 현장 영상으로 precision/recall 및 오탐 측정

처음부터 자체 모델 학습을 시작하지 않는다.

## 6. Event Engine 모듈 경계

```text
parcel_event_engine/            # 구현됨 (표준 라이브러리만 사용)
  adapters/frigate_mqtt.py      # frigate/events payload → Observation
  domain/
    observations.py             # Observation, PresenceChange
    visits.py                   # 방문 묶음 (grace·stale·재시작 처리)
    event_rules.py              # 역할 추정·의심 행동 판정, 이벤트 payload
  engine.py                     # 입력 처리·시간 진행·중복 제거 (네트워크 I/O 없음)
  config.py                     # 기준값 (임시값, 실측 후 조정)
  replay/event_replay.py        # JSONL fixture 재생 CLI
tests/
  helpers.py, test_visits.py    # SKILL.md 현재 범위 replay 시나리오
  fixtures/

# 예정
#   adapters/home_assistant.py   HA 재실 정보 → PresenceChange
#   messaging/                   MQTT 구독·발행 (라이브러리 선택 후)
#   storage/                     SQLite 상태 복구
#   main.py                      서비스 실행
```

Frigate 원본 schema는 adapter에서만 다루고 domain 로직은 표준 observation만 받는다.

## 7. 영상 clip 정책

- 필수: 이벤트 snapshot
- 선택: 이벤트 전/후 몇 초 clip
- 기본 설정: `clips_enabled: false`
- clip 기능은 Frigate recording/snapshot API를 우선 활용
- 별도 무제한 RAM buffer 금지
- 저장공간과 CPU/RAM 부하를 측정하고 설정에서 켜고 끌 수 있게 한다.

## 8. 네트워크 및 배치

Frigate는 Raspberry Pi 5에서 Docker로 실행한다. Home Assistant는 기존 장비에 둔다. Frigate 공식 설치 문서는 Frigate와 HA가 별도 장비에 있어도 같은 MQTT broker에 연결하면 통합할 수 있다고 설명한다.

MQTT broker가 이미 운영 중이면 우선 재사용한다. 다만 broker의 실제 위치, 인증, ACL, TLS, 네트워크 연결 상태를 확인한다.
