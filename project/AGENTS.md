> 이 파일의 규칙은 silent_sdk [공통 규칙](https://github.com/s1len7/silent_sdk/blob/main/AGENTS.md)에 더해 적용됨

# AGENTS.md — 택배 감시 CCTV 에이전트 지침

공통 원칙(추측 금지·"미확인" 표기, 확인이 필요한 결정, 비밀정보 취급, 파일명 규칙, 코드 스타일, 검증·보고 방식)과 Pi 환경 정보는 `../AGENTS.md`를 따른다. 이 문서는 택배 CCTV 프로젝트 고유 규칙만 다룬다. 상세 설계는 `docs/`, 이벤트 판정 규칙은 `skills/parcel-event-analysis/SKILL.md` 참고.

## 1. 목표

Raspberry Pi 5 + AI HAT+ 현관 CCTV에서 **사람의 방문을 인식해 역할을 추정**하고 Home Assistant로 알린다.

- 가족의 출입
- 택배기사로 보이는 방문
- 미확인 인물의 방문
- 의심 행동(오래 머묾, 야간 방문 등)

**택배 상자 검출과 택배별 상태 관리는 보류**한다(2026-11-01 결정). 재개 조건과 조사 결과는 `docs/IMPLEMENTATION_PLAN.md`의 택배 검출 TODO를 따른다.

최우선 원칙은 **기존 오픈소스·사전학습 모델·표준 프로토콜 재사용**이다. NVR, 객체 검출기, tracker, 알림 시스템을 새로 만들지 않고, 직접 구현은 방문 판정 규칙과 상태 관리에 한정한다.

## 2. 아키텍처

- **Pi 5:** Docker 기반 Frigate NVR + Hailo detector, Parcel Event Engine(Python), 필요 시 SQLite
- **기존 HA 장비:** Home Assistant, MQTT broker(운영 중이면 재사용), Frigate integration·자동화·모바일 알림
- Frigate, HA, Event Engine은 같은 MQTT broker에 연결한다.

데이터 흐름: 카메라 → Frigate(검출·tracking·zone) → MQTT/API → Event Engine(판정) → MQTT → HA(알림). 이벤트마다 스냅샷 저장, clip은 옵션(기본 OFF).

## 3. 환경

확인된 Pi 환경(Trixie 64-bit, 8GB, Hailo-8L `/dev/hailo0`, HailoRT 4.23.0, `hailo-all` 5.1.1)은 `../AGENTS.md` 기준이다. 프로젝트에서 추가로 확인할 항목:

| 항목 | 상태 |
| --- | --- |
| Docker | 설치됨: docker.io 26.1.5, compose 2.26.1, buildx 0.13.1. `student`는 `docker` 그룹에 추가됨(재로그인 전 세션은 `sg docker -c`) |
| Frigate 내장 HailoRT와 호스트 드라이버(`hailo-all` 5.1.1) 호환 | Frigate 0.18.2 내장 4.21.0은 불일치 → `docker/frigate/Dockerfile`로 4.23.0 교체, Hailo 감지기 동작 확인(추론 약 10ms, 2026-11-01). NPU는 Frigate 단독 사용: HailoRT 멀티프로세스 서비스로 다른 추론(Hailo Whisper)과 동시 사용 시 `hailo_pci` 커널 경고 폭주·추론 실패(2026-11-02 시험, 폐기) |
| 현관 카메라 | CSI Camera Module 3(imx708) 사용. MediaMTX 컨테이너가 RTSP로 변환(720p 10fps, 전체 화각 모드 `2304:1296`, 소프트웨어 H.264) |
| 저장장치 종류·용량 | 미확인 |
| MQTT broker 위치·인증 방식 | NAS의 Mosquitto 컨테이너, Pi는 Tailscale로 접속. 연결 미완료 → `docs/IMPLEMENTATION_PLAN.md` MQTT 연결 TODO |
| HA 설치 형태·Frigate integration | NAS에서 컨테이너로 운영 중. Frigate integration 미설치(MQTT 연결 후 진행) |

호스트의 Hailo 패키지는 교육 실습과 공유하므로, 드라이버 변경·재설치는 사용자 확인 후에만 한다.

## 4. 재사용 우선순위

1. Frigate 기본 기능: ingest, motion, detection, tracking, zones, MQTT, snapshots, recordings
2. Frigate 지원 Hailo detector 및 기본 HEF 모델 (Hailo-8L 기본: YOLOv6n)
3. Home Assistant의 재실 정보(person·device_tracker 등)
4. 기존 Frigate MQTT listener·HA integration 예제
5. 부족한 부분만 Parcel Event Engine으로 구현

참고 사례와 각 사례의 한계는 `docs/ARCHITECTURE.md` 참고.

## 5. 직접 구현 범위 (Parcel Event Engine)

- Frigate MQTT adapter, 관측값 정규화
- 방문(`visit_id`) 단위 묶음: 진입~이탈, 머문 시간, 통과한 zone
- 사람 역할 evidence 분류와 의심 행동 판정
- 중복 방지(idempotent), 재시작 후 상태 복구
- MQTT 이벤트 발행, event replay 테스트 도구

Frigate 검출/추적을 대체하는 별도 tracking pipeline은 만들지 않는다.

## 6. 분류 정책

- 객체: `person`만 다룬다. 택배 검출은 보류(§1).
- 사람 역할: `household`, `courier_likely`, `unknown`, `unclassified` (확률적, confidence·근거 함께 저장)
- 의심 행동은 역할이 아니라 방문에 붙는 판정이다. 역할과 따로 기록한다.
- 얼굴 인식은 기본 요구사항이 아니다(하향 카메라 각도). 근거가 약하면 `unknown`으로 남긴다.
- `courier_likely`는 방문 패턴에 근거한 추정이며 확정이 아니다. 배송사 식별은 범위 밖이다.

## 7. 상태·확신도

- 방문은 내부 `visit_id`로 관리하며 Frigate track ID와 동일시하지 않는다(가림·재진입으로 track ID가 바뀔 수 있음).
- 모든 이벤트는 `confirmed` / `probable` / `uncertain` 중 하나를 가진다.
- 특정인을 범죄자로 단정하지 않는다. 알림 문구는 중립적으로 쓴다(예: "현관에 미확인 인물이 오래 머물고 있습니다.").
- 상태 전이는 이벤트 로그로 보존하고 현재 상태를 재구성 가능하게 한다.

역할 판정 근거, 이벤트 종류, payload 필드는 `skills/parcel-event-analysis/SKILL.md`가 기준이다.

## 8. 저장·개인정보

- 스냅샷은 필수이며 Frigate snapshot 기능을 우선 사용한다.
- clip은 `clips_enabled: false`가 기본값. 켤 때도 Frigate recordings/API를 쓰고 무제한 RAM buffer를 만들지 않는다.
- RTSP·MQTT 자격 증명은 `.env` 등 로컬 파일로만 두고 저장소에 넣지 않는다.
- 외부 클라우드 얼굴 인식/API로 영상을 보내지 않고, 영상을 필요 이상 보관하지 않는다.

## 9. 개발 절차

각 단계 검증이 끝나기 전 다음 단계로 넘어가지 않는다. 단계별 상세·통과 기준은 `docs/IMPLEMENTATION_PLAN.md` 참고.

1. 환경 인벤토리(§3 미확인 항목)
2. Frigate + Hailo PoC
3. 사람 역할 인식 PoC(판정 근거 확보 가능성 확인)
4. Zone/추적 검증
5. Event Engine 최소 구현(MQTT adapter, event replay)
6. 방문 판정(가족·택배기사 추정·미확인·의심 행동)
7. HA 연동
8. 성능/보존 정책 측정
9. 운영 안정화(재부팅, 단절, 재연결, 중복, 복구)

## 10. 코드·테스트 (프로젝트 추가 규칙)

- type hints와 명확한 모듈 경계를 따른다.
- 로그는 구조화하고 event ID/visit ID를 포함한다.
- 모든 시간은 timezone-aware로 저장한다.
- Event Engine은 실제 카메라 없이 JSON fixture/event replay로 테스트 가능해야 한다. 필수 시나리오는 SKILL.md의 replay 테스트 목록을 따른다.
- 엔진 핵심(domain·engine·router)은 표준 라이브러리만 쓴다. 외부 패키지는 `project/.venv`에만 설치하고 `requirements.txt`에 버전을 고정한다(현재 `paho-mqtt==2.1.0`). 추가는 확인 후. venv 사용법은 `README.md`
- 테스트 (`project/`에서): `python3 -m unittest discover -s tests -t .`
- replay: `python3 -m parcel_event_engine.replay.event_replay tests/fixtures/<파일>.jsonl`

## 11. 완료 기준

- Frigate가 Hailo NPU를 실제 사용한다(CPU fallback 아님).
- 실제 카메라에서 person 검출 품질을 측정값으로 검증했다.
- 방문별로 역할 추정과 근거가 기록된다.
- 가족/택배기사 추정/미확인/의심 행동/불확실 이벤트가 구분되고 모두 스냅샷이 연결된다.
- HA 알림이 정상 수신된다.
- clip은 기본 OFF이며 설정으로 켜고 끌 수 있다.
- 재시작·중복 메시지·일시적 검출 실패에도 오탐이 통제된다.
