# CPU vs NPU 추론 성능 비교

같은 영상을 CPU(ONNX Runtime)와 NPU(Hailo-8L HEF)에 넣어 추론 시간을 비교한다.
Frigate가 쓰는 모델과 같은 YOLOv6n 계열을 사용한다.

## 무엇을 재는가

- 프레임마다 letterbox(640x640, pad 114) + RGB 변환
- CPU: `onnxruntime` `CPUExecutionProvider`로 추론
- NPU: `hailo_platform`으로 `/dev/hailo0`에서 추론
- 출력: 추론 시간 mean/median/p95, FPS, 전처리 시간, 검출 개수(참고용)

### 비교 시 주의

- **모델 가중치는 같지만 후처리 범위가 다르다.**
  - ONNX: raw 출력 `[1, 8400, 85]` (NMS 없음)
  - HEF: `parse-hef`로 확인한 결과 `YOLOX NMS BY CLASS`가 모델에 포함됨
  - 따라서 CPU 수치는 추론만, NPU 수치는 on-device NMS까지 포함한 값이다.
- 검출 개수는 두 경로의 후처리가 달라 정확도 비교용이 아니라 **파이프라인 동작 확인용**이다.
- 전처리 시간은 양쪽에 동일하게 들어가므로 추론 시간과 분리해 출력한다.

## 준비

```bash
cd ~/silent_npu/project/benchmark
./fetch_models.sh          # ONNX + HEF 내려받기 (models/, git 제외)
./capture_clip.sh -d 120   # MediaMTX RTSP에서 기준 클립 저장 (clips/, git 제외)
```

- ONNX 원본: Hailo Model Zoo `yolov6n` (2023-05-31) zip
- HEF: Frigate model cache의 `yolov6n.hef`를 우선 사용, 없으면 Model Zoo v2.14.0 HEF 다운로드

## 실행

### CPU만 (Frigate 계속 실행)

```bash
./run.sh
```

### CPU + NPU (Frigate 잠시 중지)

```bash
./run.sh --yes
```

- NPU는 Frigate가 독점하므로 `--yes`일 때만 `docker compose stop frigate` 후 실행하고, 종료 시 다시 시작한다.
- 결과는 `results/bench_<시각>.json`.

## 공정성 체크리스트

- [ ] 같은 클립, 같은 `--frames`, `--repeat` 사용
- [ ] NPU 실행 전 Frigate 중지 (`run.sh --yes`가 처리)
- [ ] CPU 경쟁 프로세스 최소화: 가능하면 `whisper`, `piper`, `homeassistant`도 잠시 중지
- [ ] Pi 온도/throttling 확인 (`vcgencmd measure_temp`, `vcgencmd get_throttled`)
- [ ] 워밍업 후 측정 (기본 10회)

## Frigate Export에 대해

현재 `docker/frigate/config/config.yml`은 `record.enabled: false`라서 Frigate UI의 Export를 쓸 recordings 소스가 없다. 기준 클립은 `capture_clip.sh`로 MediaMTX RTSP에서 직접 저장하는 방식을 권장한다. Frigate Export를 꼭 써야 하면 테스트 동안만 `record.enabled: true`로 바꿔 녹화한 뒤 Export하고 원복한다.

## 미확인

- NPU 경로(`bench.py --only npu`)는 스크립트 작성 시점에 실제 실행하지 않았다. Frigate 중지 후 첫 실행에서 확인이 필요하다.
- 서로 다른 HEF 버전(v2.14 캐시 / v2.17 컴파일본)과 ONNX 원본의 완전한 동일성은 모델 주 코드의 `network_path` 기준으로만 확인했다.
