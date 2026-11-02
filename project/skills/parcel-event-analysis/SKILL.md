# Skill: Parcel Event Analysis

## 목적

Frigate가 발행한 사람/택배 추적 이벤트를 해석해 택배별 상태와 현관 이벤트를 판정한다. 이 Skill은 Event Engine의 설계·구현·테스트 시 공통 규칙으로 사용한다.

> **현재 범위 (2026-11-01):** 사람 방문 인식과 역할 추정만 다룬다. 아래 "현재 범위: 사람 방문 판정"을 따른다.
> 택배 관련 절(Parcel identity, 권장 상태 모델, 이벤트 판정 규칙, 다중 택배, 택배 replay 테스트)은 **보류**이며, `docs/IMPLEMENTATION_PLAN.md`의 택배 검출 TODO를 재개할 때 적용한다.

## 현재 범위: 사람 방문 판정

### 방문(visit)
- Frigate `person` track이 현관 zone에 들어온 시점부터 모든 관련 track이 사라질 때까지를 하나의 `visit_id`로 묶는다.
- 가림·재진입으로 track ID가 바뀌어도 짧은 공백(grace period, 측정 후 결정) 안이면 같은 방문으로 본다.
- 방문마다 기록: 시작·종료 시각, 머문 시간, 통과한 zone 순서, 동시 인원 수, 대표 스냅샷

### 역할 근거
| 역할 | 근거 (여러 개가 맞을수록 certainty 상승) |
|---|---|
| `household` | HA 재실 정보에서 가족이 같은 시각 전후로 귀가·외출로 바뀜, 문 안쪽 zone으로 들어감 |
| `courier_likely` | 문 앞까지 왔다가 짧게 머물고 집 안으로 들어가지 않고 떠남, 주간 방문 |
| `unknown` | 사람은 확인되나 위 근거가 없음 |
| `unclassified` | 관측이 너무 짧거나 가려져 판단 불가 |

### 의심 행동 (역할과 별도 판정)
- 현관 zone에 기준 시간 이상 머묾
- 야간 시간대 방문
- 가족 부재(HA 재실 정보) 중 방문, 짧은 간격의 반복 방문
- 기준값(시간, 시간대, 간격)은 설정으로 두고 실측 후 정한다.

### 이벤트 종류
| `event_type` | 조건 |
|---|---|
| `household_arrival` / `household_departure` | `household` 근거가 있는 방문 |
| `courier_visit_likely` | `courier_likely` 근거가 있는 방문 |
| `unknown_visitor` | `unknown` 방문 |
| `suspicious_behavior` | 의심 행동 판정. 역할은 함께 기록하되 특정인을 단정하지 않는다 |
| `visit_uncertain` | 근거가 서로 충돌하거나 관측이 부족함 |

payload는 아래 "MQTT 출력 예시"와 같은 형식을 쓰되, `parcel_ids` 대신 `dwell_seconds`, `zones`, `person_count`, `suspicious_reasons`를 넣는다.

### 필수 replay 테스트 (현재 범위)
1. 가족 한 명이 귀가해 문 안으로 들어감 (HA 재실 정보 변화 포함)
2. 가족이 외출함
3. 방문자가 문 앞에 짧게 머물고 떠남 (택배기사 추정)
4. 미확인 인물이 짧게 지나감
5. 미확인 인물이 기준 시간 이상 머묾
6. 야간 방문
7. 가족 부재 중 반복 방문
8. 가림으로 track ID가 바뀌었다가 같은 사람이 다시 보임 (같은 방문 유지)
9. 가족과 방문자가 동시에 있음
10. Frigate 재시작, 동일 MQTT 메시지 중복 수신

## 입력 관측값

Frigate adapter는 원본 MQTT/API payload를 내부 표준 형식으로 변환한다.

```json
{
  "observed_at": "2026-11-01T12:00:00+09:00",
  "camera": "classroom",
  "frigate_event_id": "event-identifier",
  "track_id": "track-identifier",
  "label": "person",
  "zone_names": ["porch"],
  "box": [0.1, 0.2, 0.3, 0.6],
  "score": 0.91,
  "event_phase": "update",
  "snapshot_ref": "optional-reference"
}
```

실제 Frigate schema와 버전 차이는 adapter에서 흡수한다. 상위 이벤트 판정 로직이 Frigate payload에 직접 의존하지 않도록 한다.

## 증거 우선순위

1. 연속 프레임에서의 물체 위치/크기/appearance 일관성
2. 사람과 택배 사이의 시간적·공간적 상호작용
3. Zone 경계 통과 및 출입 방향
4. Frigate track/event lifecycle
5. Home Assistant 재실 상태 등 보조 context
6. 의복/외형/행동에 기반한 역할 추정

단일 프레임 또는 단일 track ID만으로 사람이나 택배의 정체를 확정하지 않는다.

## 사람 역할

- `household`: 가족으로 판단할 근거가 충분한 경우
- `courier_likely`: 배송/수거 행동 및 보조 단서가 배송기사와 일치하는 경우
- `unknown`: 사람이지만 역할을 신뢰성 있게 판단할 수 없는 경우
- `unclassified`: 관측 정보가 부족한 경우

역할은 변경될 수 있으며 confidence와 근거를 함께 저장한다. 얼굴 인식이 불가능하거나 신뢰도가 낮은 카메라 각도에서는 얼굴 식별을 강제하지 않는다.

## Parcel identity

각 택배는 독립적인 내부 `parcel_id`를 가진다. Frigate track ID는 tracker가 재시작하거나 가림이 발생하면 바뀔 수 있으므로 내부 parcel ID와 동일시하지 않는다.

새 관측을 기존 parcel에 연결할 때 다음을 고려한다.
- 마지막으로 관측된 위치와 시간
- bounding box 크기/위치 변화
- 외형 특징(사용 가능한 경우)
- 가림 및 재등장 가능성
- 주변 다른 parcel과의 중첩 여부

연결 신뢰도가 낮으면 기존 parcel을 임의로 합치지 않고 `candidate`를 생성해 검토한다.

## 권장 상태 모델

```text
candidate
  └─ stable presence → present
present
  ├─ household carries inside → removed_by_household
  ├─ household places return parcel → return_waiting
  ├─ courier collects return parcel → collected_by_courier
  └─ unexplained removal → removed_unexpectedly
```

상태는 단일 선형 상태 머신으로만 제한하지 않는다. 예를 들어 `return_waiting` 상태의 박스가 있는 동안 다른 `present` 택배가 추가될 수 있다. 각 parcel의 lifecycle은 독립적이다.

## 이벤트 판정 규칙

### 1. 신규 택배 배송
필요 증거:
- parcel candidate가 일정 시간 안정적으로 존재
- 사람 track이 parcel을 들고 진입하거나 배송 구역에서 parcel이 새로 나타남
- 사람 역할이 `courier_likely`일 가능성이 높음

결과:
- `parcel_delivered`
- certainty는 증거 수준에 따라 결정
- 같은 방문에서 여러 parcel이 놓이면 하나의 `visit_id`에 여러 `parcel_id` 연결

사람이 보이지 않거나 역할이 불명확하면 `parcel_placed_by_unknown` 또는 `parcel_appearance_uncertain`으로 기록한다.

### 2. 가족의 택배 반입
필요 증거:
- 기존 parcel이 `present`
- `household`로 분류된 사람이 parcel과 상호작용
- parcel이 문 안쪽 방향으로 이동하거나 실외 zone에서 사라지는 과정이 관측됨

결과:
- `parcel_taken_inside`
- 단순히 사람이 박스 앞을 지나간 경우에는 발행하지 않는다.

### 3. 가족의 반품 택배 배치
필요 증거:
- 가족으로 판단되는 사람이 parcel을 들고 현관에 접근
- parcel이 return zone에 놓이고 일정 시간 안정적으로 남음

결과:
- `return_parcel_placed`
- 기존 배송 parcel과 구별되는 새 parcel ID 부여

### 4. 택배기사의 반품 수거
필요 증거:
- `return_waiting` parcel이 존재
- `courier_likely` 사람이 parcel과 상호작용
- parcel이 배송 구역에서 제거되거나 운반되는 흐름 확인

결과:
- `return_parcel_collected`

### 5. 미확인 인물의 택배 배치
필요 증거:
- 사람 역할이 `unknown` 또는 `unclassified`
- 사람과 새 parcel 사이의 상호작용이 관측됨

결과:
- `parcel_placed_by_unknown`
- 기본적으로 중립적인 알림
- 단순 물체 출현만으로 사람의 배치 행위를 단정하지 않는다.

### 6. 기존 택배의 비정상 반출
필요 증거:
- `present` 또는 `return_waiting` parcel이 존재
- 가족/예상 수거 행동과 맞지 않는 사람의 상호작용
- parcel이 실제로 운반되거나 일정 시간 이상 사라졌다는 추가 증거

결과:
- `unexpected_parcel_removal`
- 사람과의 연관성이 확인되면 track ID 및 snapshot 포함
- 사라짐만 확인된 경우 `parcel_disappearance_uncertain`으로 분리

## 다중 택배 및 방문

- 한 방문에서 여러 parcel이 들어오면 `visit_id` 하나에 여러 `parcel_id`를 연결한다.
- 한 화면에 기존 반품 parcel과 신규 배송 parcel이 함께 있으면 서로 다른 lifecycle로 관리한다.
- 서로 다른 배송사가 연달아 방문하더라도 배송사 식별을 필수 조건으로 삼지 않는다.
- parcel 개수가 확실하지 않으면 개수를 확정하지 않고 후보 상태를 유지한다.
- 한 사람이 여러 parcel을 한 번에 옮기는 경우 각 parcel의 상태를 개별 갱신한다.

## 오탐 방지

다음 상황만으로 도난 또는 수거를 확정하지 않는다.
- 사람이나 다른 물체에 의한 일시적 가림
- 카메라 노출/야간 IR 변화
- detector confidence 하락
- Frigate track ID 변경
- Frigate 또는 카메라 재시작
- MQTT 중복/지연 메시지
- parcel이 zone 경계 밖으로 잠깐 이동
- 택배가 화면에서 사라졌으나 이동 주체가 관측되지 않은 경우

이벤트는 idempotent하게 처리한다. 동일한 Frigate event/update를 여러 번 받아도 중복 알림이 생성되지 않아야 한다.

## Certainty

- `confirmed`: 물체와 상호작용, 이동 방향, 역할 등 핵심 증거가 일관됨
- `probable`: 행동은 관측되었으나 역할/parcel identity 일부가 불확실
- `uncertain`: 핵심 증거가 누락되거나 가림/재시작 등 대안 설명이 있음

## MQTT 출력 예시

```json
{
  "event_id": "uuid",
  "event_type": "parcel_delivered",
  "timestamp": "2026-11-01T12:00:00+09:00",
  "camera": "classroom",
  "visit_id": "visit-uuid",
  "parcel_ids": ["parcel-uuid-1", "parcel-uuid-2"],
  "person_track_id": "person-track-id",
  "person_role": "courier_likely",
  "role_confidence": 0.82,
  "certainty": "probable",
  "snapshot": "/media/events/event-uuid.jpg",
  "evidence": [
    "person entered porch zone",
    "two parcel candidates became stable after person interaction"
  ]
}
```

## 필수 replay 테스트

1. 택배기사 한 명이 상자 하나 배송
2. 택배기사 한 명이 상자 여러 개 배송
3. 가족이 택배 하나 반입
4. 가족이 반품 상자 하나 배치
5. 반품 상자가 있는 동안 다른 택배사가 새 상자 배송
6. 택배기사가 반품 상자만 수거하고 신규 택배는 남김
7. 미확인 인물이 상자를 놓고 감
8. 미확인 인물이 기존 상자를 가져감
9. 사람이 상자를 가려 detection이 잠시 끊김
10. Frigate 재시작으로 track ID가 변경됨
11. 동일 MQTT 메시지가 중복 수신됨
12. parcel은 사라졌지만 이동 주체가 확인되지 않음
