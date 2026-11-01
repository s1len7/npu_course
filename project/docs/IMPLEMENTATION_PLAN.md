# 구현 계획 및 사용자 작업량 검토

## 요약

기존 소스를 최대한 재사용하면 NVR, 카메라 ingest, 기본 사람 검출, tracking, snapshot, MQTT, HA 알림 시스템을 새로 만들 필요가 없다. 현재 범위는 **사람 방문 인식과 역할 추정**(가족·택배기사 추정·미확인·의심 행동)이다. 택배 상자 검출은 보류했다(2026-11-01, 아래 택배 검출 TODO).

가장 큰 불확실성은 **얼굴 없이(하향 카메라) 가족과 방문자를 구분할 근거를 확보하는 것**이다. 그래서 먼저 HA 재실 정보, zone 통과, 머문 시간 같은 근거로 역할을 어느 정도 구분할 수 있는지 확인한다.

## 1. 사용자가 직접 해야 할 일

| 작업 | 사용자 관여 | 예상 난이도 | 예상 소요 |
|---|---|---:|---:|
| 카메라 설치/RTSP 설정 | 물리 설치 및 계정/주소 확인 | 중간 | 1~3시간 |
| 현관 영상 수집 및 검토 | 실제 환경에서 테스트 | 중간 | 며칠간 틈틈이 |
| Frigate/Hailo 설치 검증 | 에이전트가 설정 작성, 사용자가 실행/확인 | 중간 | 1~3시간 |
| Zone 위치 지정 | 화면에서 구역 확인 및 좌표 조정 | 중간 | 30~90분 |
| 역할 판정 근거 검증 | 가족 출입·방문자 시나리오 재현, HA 재실 정보 연결 | 중간 | 2~4시간 |
| 이벤트 시나리오 검증 | 실제 동작 재현 또는 녹화 영상 제공 | 중간 | 2~4시간 |
| 장기 운영/오탐 조정 | 알림 결과 확인 및 기준 조정 | 중간 | 1~2주간 관찰 |

시간은 환경이 정상이고 공개 모델을 재사용할 수 있다는 가정의 대략적인 추정치다. 하드웨어/드라이버 문제 또는 모델 학습이 필요하면 늘어난다.

## 2. 에이전트가 수행할 수 있는 일

- 공식 문서와 공개 프로젝트 조사
- Docker Compose 및 Frigate 설정 초안 작성
- MQTT adapter와 Python Event Engine 구현
- SQLite schema 및 상태 머신 구현
- event replay fixture 및 테스트 작성
- Home Assistant MQTT automation 예제 작성
- 로그 분석 및 성능 측정 명령 제시
- 모델의 라이선스/입력 규격/런타임 호환성 조사

단, 실제 카메라의 시야각/조명/사람 자세에 따른 검출 품질은 현장 영상과 사용자 검증이 필요하다. 에이전트가 영상 품질을 확인하지 않고 검출 성공을 보장해서는 안 된다.

## 3. 단계별 진행

### Phase 0 — 환경 인벤토리
Pi 하드웨어·OS·Hailo 스택은 확인 완료(`../../AGENTS.md`). 남은 확인 항목은 `../AGENTS.md` §3 표를 따른다(Docker, Frigate–드라이버 호환, 현관 카메라, 저장장치, MQTT, HA).

산출물: §3 표의 미확인 항목 해소와 호환성 결론.

### Phase 1 — Frigate + Hailo PoC
- [x] Raspberry Pi 5에 Docker 및 Frigate 설치
- [x] Hailo detector 연결 (HailoRT 4.23 교체 이미지, 추론 약 10~12ms)
- [x] 카메라 연결 (CSI Camera Module 3 → MediaMTX RTSP)
- [x] person detection / tracking 확인
- [ ] Frigate MQTT event 수신 확인 → 아래 MQTT 연결 TODO
- [x] snapshot 저장 확인

통과 기준: CPU fallback이 아니라 Hailo detector가 실제 사용되고, 영상이 안정적으로 들어오며 person track과 snapshot이 확인된다.

#### MQTT 연결 TODO
broker는 NAS의 Mosquitto 컨테이너를 쓰고, Pi(`npu-03`)는 Tailscale로 NAS(`silent-nas-ts`)에 접속한다.

- [x] Pi Tailscale 연결 (2026-11-01, 교육장 네트워크에서는 DERP 릴레이 경유)
- [x] NAS: tailnet에서 Mosquitto(1883)·HA(8123)에 닿게 하기 (2026-11-01 재확인: 1883·8123 열림, 직접 연결 약 33ms)
- [x] NAS: Tailscale ACL에서 `npu-03` → `silent-nas-ts` 접근 허용 확인 (실제 접속으로 확인, 관리 콘솔 정책은 미확인)
- [ ] NAS: Frigate 전용 MQTT 계정 생성, Pi의 `docker/frigate/.env`(`FRIGATE_MQTT_USER`, `FRIGATE_MQTT_PASSWORD`)에 입력
- [ ] Pi: `silent-nas-ts:1883` 접속·인증 확인
- [ ] Pi: `config.yml`의 `mqtt` 활성화(`host: silent-nas-ts`), `frigate/events` 발행 확인 (2026-11-01: 익명으로 활성화, `frigate/available`=online 등 상태 토픽 수신 확인. `frigate/events`는 사람 검출 시 확인 필요)
- [ ] HA: Frigate integration 설치·연결 (HA → Frigate API 접근 경로도 함께 결정)
- [ ] HA: MQTT Statestream 통합으로 `person.*` 상태 발행 (Event Engine의 가족 판정 근거, 기본 토픽 `homeassistant/statestream/person/<이름>/state`)
- [ ] Event Engine 전용 MQTT 계정 생성 → `project/engine.env`에 입력, `main.py` 실제 연결 확인

### Phase 2 — 사람 역할 인식 PoC
얼굴 인식 없이 쓸 수 있는 근거로 역할을 구분할 수 있는지 확인한다.

- 가족(`household`): HA 재실 정보(person·device_tracker)의 귀가 시점, 문 안쪽으로 들어가는 이동
- 택배기사 추정(`courier_likely`): 문 앞까지 왔다가 짧게 머물고(기준값은 측정 후 결정) 집 안으로 들어가지 않고 떠나는 패턴
- 미확인(`unknown`): 위 근거가 없는 방문
- 의심 행동: 현관 zone에 오래 머묾, 야간 방문, 가족 부재 중 반복 방문 등

통과 기준: 실제 시나리오(가족 출입, 방문자 짧은 방문, 오래 머묾)를 재현해 각 근거가 Frigate/HA 데이터로 관측되는지 확인한다. 기준값(머문 시간 등)은 측정값으로 정한다.

### Phase 3 — zone 및 observation
- `porch_zone`
- `door_threshold`
- `inside_transition`
- 필요 시 `return_zone` (택배 검출 재개 시)

Zone은 실제 화면 기준으로 조정한다. 카메라가 위에서 아래를 보는 특성상 사람의 발/손/박스가 가려지는 위치도 확인한다.

### Phase 4 — Event Engine
1. Frigate MQTT adapter
2. observation normalization
3. visit 묶음 (진입~이탈, 머문 시간, 통과 zone)
4. person role evidence (HA 재실 정보 연동 포함)
5. household / courier_likely / unknown 방문 판정
6. 의심 행동 판정 (오래 머묾, 야간, 반복 방문)
7. SQLite persistence / MQTT output / event replay

### Phase 5 — Home Assistant
- MQTT 이벤트 수신
- 이벤트별 모바일 알림
- 스냅샷 첨부 또는 URL 연결
- certainty별 알림 우선순위
- `uncertain` 이벤트는 중립적인 메시지로 제공

### Phase 6 — 운영 검증
- 카메라/Frigate/Event Engine 재시작
- MQTT 끊김/재연결
- tracker ID 변경
- 가림 및 야간
- 연속 방문, 여러 사람 동시 방문
- 저장공간 및 clip 설정
- 알림 중복/누락

### 택배 검출 TODO (보류)
2026-11-01에 범위에서 뺐다. 재개할 때 아래 조사 결과(같은 날 웹 조사)부터 검토한다.

- [ ] 경로 결정
  - 1안 Frigate+ (`package` 라벨, Hailo-8L용 YOLOv9 공식 지원, 유료 구독. 스냅샷을 Frigate+에 업로드해야 하므로 `AGENTS.md` §8 개인정보 원칙과 함께 판단)
  - 2안 YOLOv8n 직접 학습 → HEF 컴파일 (x86 Ubuntu 필요, Hailo-8L은 DFC 3.x / Model Zoo 2.x, 단일 클래스 HEF의 빈 검출 버그 보고 있음)
  - 공개 데이터셋 후보: Roboflow "package at front door"(라이선스 미확인)
- [ ] 선택한 모델이 Frigate 0.18.2 + HailoRT 4.23 교체 이미지에서 로드되는지 확인
- [ ] 실제 현관 시야에서 상자 1개·여러 개, 가림, 조명 변화로 precision/recall 측정
- [ ] parcel identity·lifecycle 구현 (SKILL.md의 택배 규칙)
- [ ] 위험 대응: 상자 가림(grace period·uncertain), 여러 상자 겹침(독립 추적·후보 상태)

## 4. 자체 개발량 예상

### 기존 모델/소스가 충분한 경우
- Frigate 설정/배포: 낮음
- Event Engine: 중간
- HA 자동화: 낮음
- 모델 학습: 불필요할 수 있음
- 총 직접 개발 핵심: 방문 판정과 역할 추정 로직

### 택배 검출을 재개하고 공개 모델이 맞지 않는 경우
추가 작업:
- 데이터셋 수집 및 annotation
- fine-tuning 또는 모델 학습
- Hailo 변환/컴파일 및 Frigate custom model 통합
- 반복 평가와 오탐 개선

이 경우 가장 많은 시간은 코드보다 영상 데이터 수집/라벨링/검증에 들어갈 수 있다.

## 5. 위험 및 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| 하향 카메라에서 얼굴이 보이지 않음 | 가족 식별 한계 | 얼굴 인식을 필수 기능에서 제외, HA 재실 정보·행동 패턴으로 보완 |
| 사람 track ID가 바뀜 | 역할/상호작용 연결 오류 | Frigate track ID와 내부 identity 분리 |
| 택배기사와 방문자 구분 어려움 | 잘못된 정상/비정상 판정 | 역할 confidence 및 중립 알림 |
| Pi 저장장치 쓰기 부담 | 수명/성능 저하 | snapshot/recording retention 제한 |
| Frigate 내장 HailoRT와 호스트 드라이버(`hailo-all` 5.1.1) 불일치 | detector 실행 실패, 교육 실습 환경 손상 | Frigate Trixie 안내 확인, 드라이버 변경은 사용자 확인 후 |
