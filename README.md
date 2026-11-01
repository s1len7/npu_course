# NPU 기반 온디바이스 AI 모델 경량화·추론 실무

## 교육 개요

| 항목 | 내용 |
| --- | --- |
| 교육명 | NPU 기반 온디바이스 AI 모델 경량화·추론 실무 |
| 기간 | 2026.10.25(일) ~ 2026.11.14(토), 09:00~18:00 (총 40시간) |
| 휴강일 | 10/31(토) |
| 강사 | 임보연 강사님 |
| 방식 | 대면 교육 |
| 교육장 | 서울특별시 영등포구 양평로 25길 8, 4층 (어반322 410호) · 9호선 선유도역 8번 출구 도보 5분 |
| 준비물 | 노트북, 키보드·마우스 (USB-C 유선, 블루투스 X) |

- **교육 안내:** https://event-us.kr/itsaict/event/136250
- **과정 오픈채팅방:** https://open.kakao.com/o/gGnt49Ri (접속코드: 수신 이메일 참고<!-- `ITSA` -->)
- 강의자료
  - https://buly.kr/Yhbi2n
  - https://drive.google.com/drive/folders/1C3t3EdHRBjS6obvIa70ETaPk2FNaKo_j?usp=sharing

> 교육 시작 10분 전까지 입실. 건물 내 주차는 가능하지만 주차비는 지원되지 않습니다.

<details>
<summary>교육 안내 이미지 (원본 링크)</summary>

![교육 안내 1](https://eventusstorage.blob.core.windows.net/evs/Image/itsaict/136250/ProjectInfo/813f13ddee734213a07427fd4abd07e3.jpg)
![교육 안내 2](https://eventusstorage.blob.core.windows.net/evs/Image/itsaict/136250/ProjectInfo/f60bb32d2eb44e7794fd6b02f1bdc051.jpg)
![교육 안내 3](https://eventusstorage.blob.core.windows.net/evs/Image/itsaict/136250/ProjectInfo/a167b03d9f7a4abfbfbb04138d62909c.jpg)

</details>

## 목차

- [교육 개요](#교육-개요)
- [0. 워크스페이스 구조](#0-워크스페이스-구조)
- [1. PC 실습 환경](#1-pc-실습-환경)
- [2. IDE](#2-ide)
- [3. 실습 장비: Raspberry Pi 5 + AI HAT+](#3-실습-장비-raspberry-pi-5--ai-hat)
- [메모](#메모)

---

## 0. 워크스페이스 구조

```
npu_course/
├── README.md              # 교육 정리 문서 (이 파일)
├── .vscode/
│   └── settings.json      # VS Code 기본 인터프리터(npu_env)·기본 터미널(cmd) 지정
├── npu_env/               # Python 3.12 가상환경 (PyTorch, ONNX 등 설치)
├── day1/
│   └── test.py            # 환경 확인: NumPy·Pandas·PyTorch 버전 출력
└── backup/                # 실습용 Raspberry Pi 5에 기본 세팅돼 있던 파일
    ├── npu.zip            # 배포 원본 압축 파일
    └── npu/               # npu.zip 압축 해제본
        ├── README_설치순서.md   # 설치·점검 순서 안내 (v3)
        ├── npu_setup.sh         # 1~3단계 설치 (OS·EEPROM → 카메라·hailo-all → Hailo Apps·모델·실습 폴더)
        ├── npu_check1.sh        # 1단계 점검: OS, 호스트명, 네트워크, EEPROM
        ├── npu_check2.sh        # 2단계 점검: 카메라, NPU, 공식 YOLO/Pose 데모
        ├── npu_check3.sh        # 3단계 점검: Hailo Apps, HEF 모델, Detection/Simple/Pose 데모
        └── SHA256SUMS.txt       # 스크립트 체크섬 (sha256sum -c 로 확인 가능)
```

- `npu_env/`는 각자 PC에서 다시 만드는 폴더이므로 공유·백업 대상에서 빼도 됩니다.
- `backup/`의 스크립트는 Pi에서 실행되는 것으로, PC에서는 참고용입니다. 자세한 내용은 [3-5](#3-5-교육용-사전-준비물) 참고.

---

## 1. PC 실습 환경

| 항목 | 버전 |
| --- | --- |
| Python | 3.12.10 |
| 가상환경 | `npu_env` (이 폴더 안) |
| PyTorch | 2.12.1 (CPU) / torchvision 0.27.1 |
| ONNX | onnx, onnxruntime, onnxscript |

### 1-1. Python 설치

[python.org](https://www.python.org/downloads/)에서 Python **3.12.10**을 내려받아 설치합니다.

### 1-2. 작업 폴더와 가상환경 만들기

명령 프롬프트(cmd)에서 실행합니다.

```bat
cd /d "%USERPROFILE%\OneDrive\바탕 화면"
mkdir npu_course
cd npu_course

python -m venv npu_env
npu_env\Scripts\activate.bat
```

활성화되면 프롬프트 앞에 `(npu_env)`가 표시됩니다. 비활성화는 `deactivate`.

### 1-3. 패키지 설치

가상환경을 활성화한 상태에서 실행합니다.

```bat
python -m pip install --upgrade pip

# 기본 패키지
pip install numpy pandas matplotlib scikit-learn pillow

# PyTorch (버전 고정, CPU 전용 빌드)
pip install torch==2.12.1 torchvision==0.27.1 --index-url https://download.pytorch.org/whl/cpu

# ONNX 변환(onnx, onnxscript)과 추론(onnxruntime)
pip install onnx onnxruntime onnxscript
```

다른 PyTorch 버전 조합은 [PyTorch 이전 버전 안내](https://pytorch.org/get-started/previous-versions/)에서 확인할 수 있습니다.

---

## 2. IDE

강의는 PyCharm으로 진행하지만, 개인적으로는 VS Code로 대신 진행하기로 결정했습니다.

### VS Code (사용)

- 확장: Python, Remote - SSH
- 워크스페이스 인터프리터: `.vscode/settings.json`에서 `npu_env\Scripts\python.exe`로 지정
- 터미널 기본값: `.vscode/settings.json`에서 명령 프롬프트로 지정 → 새 터미널을 열면 `npu_env`가 자동 활성화
- 다른 인터프리터가 잡히면 `Ctrl+Shift+P` → **Python: Select Interpreter** → `npu_env`

### PyCharm (강의 기준)

- [PyCharm 이전 버전 다운로드](https://www.jetbrains.com/pycharm/download/other/#releases-2025)에서 **2025.3** 버전 설치 (이 장비: 2025.3.6.1)
- `npu_course` 폴더를 열고 인터프리터를 `npu_env\Scripts\python.exe`로 지정

---

## 3. 실습 장비: Raspberry Pi 5 + AI HAT+

### 3-1. 접속 정보

| 항목 | 값 |
| --- | --- |
| 호스트 이름 | `npu-03` |
| IP | `192.168.0.65` (교육장 네트워크, 바뀔 수 있음) |
| 기본 계정 | ID `student` / PW `asdf1234!` |

### 3-2. SSH 접속

VS Code의 **Remote - SSH** 확장으로, 기본 계정(ID `student` / PW `asdf1234!`)으로 접속합니다.

1. `Ctrl+Shift+P` → **Remote-SSH: Connect to Host…**
2. `student@192.168.0.65` 입력
3. 플랫폼을 물으면 **Linux** 선택, 비밀번호 입력
4. 처음 접속할 때는 Pi에 VS Code 서버가 설치되어 1분 정도 걸립니다.

- IP는 교육장 네트워크에서 바뀔 수 있으니 접속이 안 되면 Pi에서 `hostname -I`로 확인합니다.
- VS Code는 다시 연결할 때마다 비밀번호를 물어봅니다.

### 3-3. 장비 구성

| 항목 | 내용 |
| --- | --- |
| 보드 | Raspberry Pi 5 (8GB) |
| OS | Raspberry Pi OS Trixie (Debian 13), 64-bit |
| NPU | AI HAT+ 13 TOPS (**Hailo-8L**), PCIe Gen3 x1, `/dev/hailo0` |
| 카메라 | Camera Module 3 (imx708) |
| Python | 3.13.5 (시스템) |

### 3-4. AI HAT 관련 소프트웨어

| 구성 | 버전 / 위치 |
| --- | --- |
| `hailo-all` | 5.1.1 (HailoRT 4.23.0, PCIe 드라이버, TAPPAS core 5.1.0 포함) |
| 서비스 | `hailort.service` 실행 중 |
| 카메라 연동 | rpicam-apps 1.14.0 (`rpicam-apps-hailo-postprocess` 포함), picamera2 0.3.38 |
| Hailo Apps | `~/hailo-apps` (Release 26.10.0), 가상환경 `venv_hailo_apps` |
| 모델(HEF) | `/usr/share/hailo-models` (기본), `/usr/local/hailo/resources` (Hailo Apps, 41개) |

카메라 확인 (Pi 데스크톱 터미널):

```bash
rpicam-hello --list-cameras   # 카메라 인식 확인
rpicam-hello -t 0             # 미리보기 창 (Ctrl+C로 종료)
```

Hailo Apps 데모 실행:

```bash
cd ~/hailo-apps
source setup_env.sh
hailo-detect --input rpi --show-fps
hailo-detect-simple --input rpi --show-fps
```

### 3-5. 교육용 사전 준비물

- `~/npu_setup.sh`, `~/npu_check1~3.sh`, `~/README_설치순서.md`: 장비 설치·점검 스크립트 (이 장비는 3단계까지 완료, 사본은 워크스페이스 `backup/`)
- `~/npu_course`: 실습 폴더 (아직 비어 있음)
  - `00_check` ~ `07_project`: 카메라 → 추론 → ONNX → 양자화 → Hailo → 벤치마크 → 프로젝트
  - `data/{images,videos}`, `models/{pytorch,onnx,hailo}`, `results`, `logs`
  - `system_info`: 설치 당시 OS·커널·HailoRT·패키지 버전 기록

### 3-6. 참고

- Pi에는 PyTorch와 Hailo 컴파일러(Dataflow Compiler)가 없습니다. 모델 학습·ONNX 변환은 PC에서, `.hef` 실행은 Pi에서 하는 구조로 보입니다. (ONNX → HEF 컴파일은 x86 Linux 필요)
- numpy 버전이 환경마다 다릅니다: 시스템 2.2.4 / `venv_hailo_apps` 1.26.4.

### 3-7. Hailo Model Zoo

이 Pi(HailoRT 4.23.0)와 맞는 버전은 **v2.17** 태그입니다 (Dataflow Compiler 3.33.0 / HailoRT 4.23.0, Suite 2025-10 계열과 동일).

- 저장소 (v2.17): https://github.com/hailo-ai/hailo_model_zoo/tree/v2.17
- Hailo-8L 모델 목록: https://github.com/hailo-ai/hailo_model_zoo/tree/v2.17/docs/public_models/HAILO8L
  - 분류: https://github.com/hailo-ai/hailo_model_zoo/blob/v2.17/docs/public_models/HAILO8L/HAILO8L_classification.rst
  - 객체 탐지: https://github.com/hailo-ai/hailo_model_zoo/blob/v2.17/docs/public_models/HAILO8L/HAILO8L_object_detection.rst
- 저장소 메인 (최신): https://github.com/hailo-ai/hailo_model_zoo
- 릴리스 목록: https://github.com/hailo-ai/hailo_model_zoo/releases
- Hailo Model Explorer: https://hailo.ai/products/hailo-software/model-explorer/

- Hailo-8/8L은 **v2.x**, Hailo-10/15는 **v5.x** 계열입니다. v5.x는 Hailo-8L용이 아닙니다.
- v2.20.0은 HailoRT 4.24.0 기준이라 이 Pi(4.23.0)와 버전이 다릅니다.
- 모델 목록 표에서 미리 컴파일된 HEF를 받으면 DFC 없이 Pi에서 바로 실행할 수 있습니다. (Pi에서 실제 실행은 미확인)

### 3-8. 원격 접속: Tailscale

교육장 밖에서도 Pi에 접속할 수 있도록 Tailscale이 호스트에 직접 설치되어 있습니다. Docker 컨테이너가 아니라 시스템 패키지입니다.

| 항목 | 값 |
| --- | --- |
| 설치 방식 | 공식 apt 저장소 (`pkgs.tailscale.com/stable/debian trixie`), 패키지 `tailscale` 1.104.4 |
| 서비스 | `tailscaled.service` 실행 중, 부팅 시 자동 시작 |
| Tailscale 호스트 이름 | `npu-03` |
| Tailscale IP | `100.119.172.74` (기기를 tailnet에서 지우지 않으면 유지) |
| 설정 | Tailscale SSH·서브넷 라우팅·exit node 사용 안 함. `tailscale serve`로 tailnet에만 노출: `5000` → Frigate 내부 API(NAS Home Assistant Frigate integration용), `8123` → Pi의 Home Assistant(`project/docker/homeassistant`). 둘 다 Docker에서는 `127.0.0.1`에만 publish |

접속할 PC도 같은 tailnet에 로그인되어 있어야 합니다. 이 경우 교육장 IP 대신 Tailscale IP로 SSH 접속합니다.

```bash
ssh student@100.119.172.74
```

- VS Code Remote - SSH에서는 [3-2](#3-2-ssh-접속)의 2단계에서 `student@100.119.172.74`를 입력합니다.
- 상태 확인: `tailscale status`, `tailscale ip -4`
- Tailscale SSH(`--ssh`)는 꺼져 있으므로, 인증은 Pi의 OpenSSH(비밀번호 또는 키)로 합니다.

---

## 메모

<!-- 이 문장은 교육이랑 상관없이, 나중에 anti gravity ide 사용해보기(이건 지우지마) -->

<!--
[개인 설정] SSH 키 접속 (이 PC에만 해당)

- PC에 SSH 키(~/.ssh/id_ed25519)를 만들어 Pi(npu-03)의 ~/.ssh/authorized_keys에 등록해 둠 → 비밀번호 없이 접속
- ~/.ssh/config:

    Host rpi5
        HostName 192.168.0.65
        User student
        IdentityFile ~/.ssh/id_ed25519
        IdentitiesOnly yes

- VS Code: Ctrl+Shift+P → Remote-SSH: Connect to Host… → rpi5
- VS Code 사용자 설정에 remote.SSH.remotePlatform { "rpi5": "linux" } 추가함
- IP가 바뀌면 HostName만 수정
- 장비 반납 시 Pi의 ~/.ssh/authorized_keys에서 이 PC의 키(silent@thinkpad-s2-2g)를 지울 것
-->
