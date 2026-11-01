# 구현 계획 및 사용자 작업량 검토

## 요약

기존 소스를 최대한 재사용하면 NVR, 카메라 ingest, 기본 사람 검출, tracking, snapshot, MQTT, HA 알림 시스템을 새로 만들 필요가 없다. 가장 큰 불확실성과 직접 작업량은 **현관 위에서 아래로 내려다보는 각도에서 택배 상자를 안정적으로 검출하는 것**과 **사람 역할 및 택배별 lifecycle을 정확히 판정하는 것**이다.

따라서 첫 목표는 전체 시스템 완성이 아니라, 실제 카메라에서 Frigate + Hailo가 사람과 택배 후보를 충분히 검출하는지 확인하는 것이다.

## 1. 사용자가 직접 해야 할 일

| 작업 | 사용자 관여 | 예상 난이도 | 예상 소요 |
|---|---|---:|---:|
| 카메라 설치/RTSP 설정 | 물리 설치 및 계정/주소 확인 | 중간 | 1~3시간 |
| 현관 영상 수집 및 검토 | 실제 환경에서 테스트 | 중간 | 며칠간 틈틈이 |
| Frigate/Hailo 설치 검증 | 에이전트가 설정 작성, 사용자가 실행/확인 | 중간 | 1~3시간 |
| Zone 위치 지정 | 화면에서 구역 확인 및 좌표 조정 | 중간 | 30~90분 |
| package detector 검증 | 샘플 장면 제공/오탐 확인 | 중간~높음 | 2~6시간 |
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

단, 실제 카메라의 시야각/조명/택배 모양에 따른 검출 품질은 현장 영상과 사용자 검증이 필요하다. 에이전트가 영상 품질을 확인하지 않고 검출 성공을 보장해서는 안 된다.

## 3. 단계별 진행

### Phase 0 — 환경 인벤토리
Pi 하드웨어·OS·Hailo 스택은 확인 완료(`../../AGENTS.md`). 남은 확인 항목은 `../AGENTS.md` §3 표를 따른다(Docker, Frigate–드라이버 호환, 현관 카메라, 저장장치, MQTT, HA).

산출물: §3 표의 미확인 항목 해소와 호환성 결론.

### Phase 1 — Frigate + Hailo PoC
- Raspberry Pi 5에 Docker 및 Frigate 설치
- Hailo detector 연결
- 카메라 RTSP 연결
- person detection / tracking 확인
- Frigate MQTT event 수신 확인
- snapshot 저장 확인

통과 기준: CPU fallback이 아니라 Hailo detector가 실제 사용되고, 영상이 안정적으로 들어오며 person track과 snapshot이 확인된다.

### Phase 2 — package detector PoC
- 기본 모델의 label map과 실제 검출 결과 확인
- 공개 package detector 후보 조사
- 실제 현관 시야에서 상자 1개/여러 개, 가림, 조명 변화 테스트
- 필요하면 custom model 도입 여부 판단

통과 기준: 상자 검출 precision/recall이 이벤트 엔진을 만들 가치가 있을 정도인지 확인한다. 숫자를 측정하지 않고 "잘 된다"고 판단하지 않는다.

### Phase 3 — zone 및 observation
- `porch_zone`
- `door_threshold`
- `inside_transition`
- 필요 시 `return_zone`

Zone은 실제 화면 기준으로 조정한다. 카메라가 위에서 아래를 보는 특성상 사람의 발/손/박스가 가려지는 위치도 확인한다.

### Phase 4 — Event Engine
1. Frigate MQTT adapter
2. observation normalization
3. parcel identity 및 독립 lifecycle
4. person role evidence
5. delivery / household pickup / return placement / courier collection
6. unknown placement / unexpected removal
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
- 다중 택배와 연속 방문
- 저장공간 및 clip 설정
- 알림 중복/누락

## 4. 자체 개발량 예상

### 기존 모델/소스가 충분한 경우
- Frigate 설정/배포: 낮음
- Event Engine: 중간
- HA 자동화: 낮음
- 모델 학습: 불필요할 수 있음
- 총 직접 개발 핵심: 택배 lifecycle과 이벤트 판정 로직

### package detector가 맞지 않는 경우
추가 작업:
- 데이터셋 수집 및 annotation
- fine-tuning 또는 모델 학습
- Hailo 변환/컴파일 및 Frigate custom model 통합
- 반복 평가와 오탐 개선

이 경우 가장 많은 시간은 코드보다 영상 데이터 수집/라벨링/검증에 들어갈 수 있다.

## 5. 위험 및 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| 기본 모델이 parcel을 검출하지 못함 | 배송/반출 판단 불가 | 별도 package model PoC |
| 하향 카메라에서 얼굴이 보이지 않음 | 가족 식별 한계 | 얼굴 인식을 필수 기능에서 제외 |
| 사람 track ID가 바뀜 | 역할/상호작용 연결 오류 | Frigate track ID와 내부 identity 분리 |
| 택배가 가려짐 | 오탐 제거/도난 | grace period 및 uncertain 상태 |
| 여러 박스가 겹침 | parcel ID 병합/분리 오류 | parcel별 독립 추적, 후보 상태 |
| 택배기사와 방문자 구분 어려움 | 잘못된 정상/비정상 판정 | 역할 confidence 및 중립 알림 |
| Pi 저장장치 쓰기 부담 | 수명/성능 저하 | snapshot/recording retention 제한 |
| Frigate 내장 HailoRT와 호스트 드라이버(`hailo-all` 5.1.1) 불일치 | detector 실행 실패, 교육 실습 환경 손상 | Frigate Trixie 안내 확인, 드라이버 변경은 사용자 확인 후 |
