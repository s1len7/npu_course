> 이 파일의 규칙은 silent_sdk [공통 규칙](https://github.com/s1len7/silent_sdk/blob/main/AGENTS.md)에 더해 적용됨

# AGENTS.md — 택배 감시 CCTV 에이전트 지침

공통 원칙(추측 금지·"미확인" 표기, 확인이 필요한 결정, 비밀정보 취급, 파일명 규칙, 코드 스타일, 검증·보고 방식)과 Pi 환경 정보는 `../AGENTS.md`를 따른다. 이 문서는 택배 CCTV 프로젝트 고유 규칙만 다룬다. 상세 설계는 `docs/`, 이벤트 판정 규칙은 `skills/parcel-event-analysis/SKILL.md` 참고.

## 1. 목표

Raspberry Pi 5 + AI HAT+ 현관 CCTV에서 사람과 택배의 움직임을 분석해 다음 이벤트를 판정하고 Home Assistant로 알린다.

- 택배기사의 신규 택배 배송
- 가족의 택배 반입 / 반품 택배 배치
- 택배기사의 반품 택배 수거
- 미확인 인물의 택배 배치
- 택배의 비정상 반출 등 의심스러운 상호작용

최우선 원칙은 **기존 오픈소스·사전학습 모델·표준 프로토콜 재사용**이다. NVR, 객체 검출기, tracker, 알림 시스템을 새로 만들지 않고, 직접 구현은 택배 업무 규칙과 상태 관리에 한정한다.

## 2. 아키텍처

- **Pi 5:** Docker 기반 Frigate NVR + Hailo detector, Parcel Event Engine(Python), 필요 시 SQLite
- **기존 HA 장비:** Home Assistant, MQTT broker(운영 중이면 재사용), Frigate integration·자동화·모바일 알림
- Frigate, HA, Event Engine은 같은 MQTT broker에 연결한다.

데이터 흐름: 카메라 → Frigate(검출·tracking·zone) → MQTT/API → Event Engine(판정) → MQTT → HA(알림). 이벤트마다 스냅샷 저장, clip은 옵션(기본 OFF).

## 3. 환경

확인된 Pi 환경(Trixie 64-bit, 8GB, Hailo-8L `/dev/hailo0`, HailoRT 4.23.0, `hailo-all` 5.1.1)은 `../AGENTS.md` 기준이다. 프로젝트에서 추가로 확인할 항목:

| 항목 | 상태 |
| --- | --- |
| Docker | 설치됨: docker.io 26.1.5, compose 2.26.1, buildx 0.13.1. `student`는 `docker` 그룹이 아님 |
| Frigate 내장 HailoRT와 호스트 드라이버(`hailo-all` 5.1.1) 호환 | Frigate 0.18.2 내장 4.21.0은 불일치 → `docker/frigate/Dockerfile`로 4.23.0 교체, Hailo 감지기 동작 확인(추론 약 10ms, 2026-11-01). 교육 데모와 NPU 동시 사용은 미확인 |
| 현관 카메라 | CSI Camera Module 3(imx708) 사용. MediaMTX 컨테이너가 RTSP로 변환(720p 10fps, 전체 화각 모드 `2304:1296`, 소프트웨어 H.264) |
| 저장장치 종류·용량 | 미확인 |
| MQTT broker 위치·인증 방식 | NAS의 Mosquitto 컨테이너, Pi는 Tailscale로 접속. 연결 미완료 → `docs/IMPLEMENTATION_PLAN.md` MQTT 연결 TODO |
| HA 설치 형태·Frigate integration | NAS에서 컨테이너로 운영 중. Frigate integration 미설치(MQTT 연결 후 진행) |

호스트의 Hailo 패키지는 교육 실습과 공유하므로, 드라이버 변경·재설치는 사용자 확인 후에만 한다.

## 4. 재사용 우선순위

1. Frigate 기본 기능: ingest, motion, detection, tracking, zones, MQTT, snapshots, recordings
2. Frigate 지원 Hailo detector 및 기본 HEF 모델 (Hailo-8L 기본: YOLOv6n)
3. Hailo Model Zoo 사전학습/컴파일 모델
4. 현관 택배 검출용 공개 모델/프로젝트
5. 기존 Frigate MQTT listener·HA integration 예제
6. 부족한 부분만 Parcel Event Engine으로 구현

참고 사례와 각 사례의 한계는 `docs/ARCHITECTURE.md` 참고.

## 5. 직접 구현 범위 (Parcel Event Engine)

- Frigate MQTT adapter, 관측값 정규화
- parcel별 독립 ID·lifecycle, 사람 역할 evidence 분류
- 방문(`visit_id`)과 다중 택배 연결
- 배치/반입/반품 배치/수거/비정상 반출 판정
- 중복 방지(idempotent), 재시작 후 상태 복구
- MQTT 이벤트 발행, event replay 테스트 도구

Frigate 검출/추적을 대체하는 별도 tracking pipeline은 만들지 않는다.

## 6. 분류 정책

- 객체: `person`, `parcel`(또는 검증된 custom label). COCO의 `suitcase`·`backpack`·`handbag` 등을 택배로 임의 매핑하지 않는다. 실제 현관 영상으로 검증한 뒤 custom model 도입을 결정한다.
- 사람 역할: `household`, `courier_likely`, `unknown`, `unclassified` (확률적, confidence·근거 함께 저장)
- 얼굴 인식은 기본 요구사항이 아니다(하향 카메라 각도). 근거가 약하면 `unknown`으로 남긴다.
- `courier_likely`는 확정이 아니며 배송사 식별은 범위 밖이다.

## 7. 상태·확신도

- 모든 택배는 독립 `parcel_id`를 가지며, Frigate track ID와 동일시하지 않는다.
- 일시적 검출 실패·가림·tracker ID 변경만으로 사라졌다고 판정하지 않는다.
- 모든 이벤트는 `confirmed` / `probable` / `uncertain` 중 하나를 가진다.
- 사라짐만으로 도난을 확정하지 않는다. 알림 문구는 중립적으로 쓴다(예: "미확인 인물이 택배에 접근했습니다.").
- 상태 전이는 이벤트 로그로 보존하고 현재 상태를 재구성 가능하게 한다.

상태 목록, 판정 규칙, 이벤트 payload 필드는 `skills/parcel-event-analysis/SKILL.md`가 기준이다.

## 8. 저장·개인정보

- 스냅샷은 필수이며 Frigate snapshot 기능을 우선 사용한다.
- clip은 `clips_enabled: false`가 기본값. 켤 때도 Frigate recordings/API를 쓰고 무제한 RAM buffer를 만들지 않는다.
- RTSP·MQTT 자격 증명은 `.env` 등 로컬 파일로만 두고 저장소에 넣지 않는다.
- 외부 클라우드 얼굴 인식/API로 영상을 보내지 않고, 영상을 필요 이상 보관하지 않는다.

## 9. 개발 절차

각 단계 검증이 끝나기 전 다음 단계로 넘어가지 않는다. 단계별 상세·통과 기준은 `docs/IMPLEMENTATION_PLAN.md` 참고.

1. 환경 인벤토리(§3 미확인 항목)
2. Frigate + Hailo PoC
3. 택배 검출 PoC
4. Zone/추적 검증
5. Event Engine 최소 구현(MQTT adapter, event replay)
6. 단일 택배 lifecycle
7. 다중 택배/복수 방문
8. HA 연동
9. 성능/보존 정책 측정
10. 운영 안정화(재부팅, 단절, 재연결, 중복, 복구)

## 10. 코드·테스트 (프로젝트 추가 규칙)

- type hints와 명확한 모듈 경계를 따른다.
- 로그는 구조화하고 event ID/parcel ID를 포함한다.
- 모든 시간은 timezone-aware로 저장한다.
- Event Engine은 실제 카메라 없이 JSON fixture/event replay로 테스트 가능해야 한다. 필수 시나리오는 SKILL.md의 replay 테스트 목록을 따른다.

## 11. 완료 기준

- Frigate가 Hailo NPU를 실제 사용한다(CPU fallback 아님).
- 실제 카메라에서 person·package 검출 품질을 측정값으로 검증했다.
- 박스별 ID와 상태가 독립적으로 유지된다.
- 정상/의심/불확실 이벤트가 구분되고 모두 스냅샷이 연결된다.
- HA 알림이 정상 수신된다.
- clip은 기본 OFF이며 설정으로 켜고 끌 수 있다.
- 재시작·중복 메시지·일시적 검출 실패에도 오탐이 통제된다.
