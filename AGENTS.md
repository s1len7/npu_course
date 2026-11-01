> 이 파일의 규칙은 silent_sdk [공통 규칙](https://github.com/s1len7/silent_sdk/blob/main/AGENTS.md)에 더해 적용됨

# AGENTS.md

이 저장소에서 작업하는 에이전트를 위한 지침. 상세 배경은 `README.md` 참고.

## 기본 원칙

- 추측으로 사실을 만들지 말 것. 확인하지 못한 내용은 "미확인"으로 표시한다.
- 요청한 범위만 수정한다. 작업 중 발견한 다른 문제는 고치지 말고 보고만 한다.
- 커밋·푸시는 요청받았을 때만 한다. (현재 이 폴더는 git 저장소가 아니다.)
- 설계는 가능한 단순하게 하되, 예외 처리는 꼼꼼히 한다.

## 확인이 필요한 결정

아래는 실행 전에 선택지와 근거·영향을 먼저 제시하고 사용자 확인을 받는다.

- 파일·폴더·기능·설정 항목 삭제 (`backup/`, `npu_env/` 포함)
- 여러 대안 중 하나를 고르는 일 (패키지 버전, 모델 형식, 폴더 구조 등)
- 사용자에게 보이는 동작 변경 (스크립트 출력 의미, 기본값, 실행 순서)
- `README.md`에 적힌 경로·명령·장비 이름처럼 사용자가 참조하는 식별자 변경

승인 범위는 좁게 해석한다. 지우기 전에 왜 있는지부터 확인하고, 비슷한 것이 둘이면 용도·제약을 비교한 뒤 판단한다.

## 프로젝트 개요

"NPU 기반 온디바이스 AI 모델 경량화·추론 실무" 교육(2026-10-25 ~ 2026-11-14) 실습 워크스페이스.
PC(Windows)에서 모델 준비·변환을 하고, Raspberry Pi 5 + AI HAT+(Hailo-8L)에서 추론을 실행하는 구조.

- PC: 학습·ONNX 변환·양자화 (PyTorch CPU)
- Pi: `.hef` 컴파일 결과물 실행, 카메라/Hailo 데모
- Pi에는 PyTorch와 Hailo Dataflow Compiler가 없고, ONNX → HEF 컴파일은 x86 Linux가 필요하다.

## 환경

| 항목 | 값 |
| --- | --- |
| OS | Windows (PowerShell 5.1 / cmd) |
| Python | 3.12.10, 가상환경 `npu_env/` |
| 인터프리터 | `npu_env\Scripts\python.exe` (`.vscode/settings.json`에 고정) |
| 기본 터미널 | Command Prompt, 열면 `npu_env` 자동 활성화 |
| 주요 패키지 | numpy, pandas, matplotlib, scikit-learn, pillow, torch 2.12.1+cpu, torchvision 0.27.1, onnx, onnxruntime, onnxscript |

## 구조

```
npu_course/
├── README.md          # 교육 정리 문서
├── AGENTS.md          # 이 파일
├── .vscode/           # 인터프리터·터미널 설정
├── npu_env/           # Python 3.12 가상환경 (생성물, 공유/백업 대상 아님)
├── day1/test.py       # 환경 확인 스크립트
└── backup/            # Pi 기본 세팅 파일 사본 (읽기 전용 참고자료)
    ├── npu.zip
    ├── npu/           # npu_setup.sh, npu_check1~3.sh, README_설치순서.md, SHA256SUMS.txt
    └── npu_course/    # system_info: 설치 당시 OS/커널/HailoRT/패키지 버전 기록
```

## 명령

```bat
:: 가상환경 활성화 (cmd, 새 터미널은 자동)
npu_env\Scripts\activate.bat

:: 환경 확인
python day1\test.py
```

```powershell
# PowerShell에서 직접 실행할 때
& ".\npu_env\Scripts\python.exe" .\day1\test.py
```

## 작업 규칙

- `npu_env/`는 재생성 가능한 산출물이다. 내용을 직접 수정·패치하지 말고, 패키지 변경은 `python -m pip`로만 한다.
- `backup/`은 Pi 원본 사본이다. 사용자가 명시적으로 요청하지 않으면 수정하지 않는다. 스크립트는 Pi용 bash이며 PC에서는 참고용이다.
- `backup/npu.zip`과 `SHA256SUMS.txt`는 무결성 확인용이므로 재압축·재생성하지 않는다.
- `README.md`의 접속 정보(계정, 비밀번호, SSH 키 경로, 개인 메모)를 새 파일이나 로그로 복제하지 않는다.
- 비밀번호·토큰·키를 파일, 로그, 콘솔 출력에 남기지 않는다. 로그를 남기려고 환경변수나 설정을 통째로 덤프하지 않는다.
- 새로 만드는 파일·폴더 이름에는 공백과 한글을 쓰지 않는다(영문·숫자·`-`·`_`만). 기존 경로(`바탕 화면`)는 그대로 두고, 다룰 때는 항상 따옴표로 감싼다.
- 삭제·대량 이동 전에 `Test-Path`로 대상 경로를 먼저 확인한다.
- 줄바꿈: Pi용 `.sh`는 LF, Windows용 `.bat`·`.ps1`은 CRLF.

## 코드 스타일

- Python: PEP 8, 문자열은 가능한 f-string, 불필요한 제어문자(`\n` 남발) 대신 별도 `print` 사용.
- Bash: Google Shell Style Guide, ShellCheck 경고가 없도록 작성.
- 주석·문서·커밋 메시지는 한국어, 로그와 콘솔 출력 메시지는 영어로 쓴다.
- 코드 주석은 꼭 필요할 때만 남긴다.

## Raspberry Pi 작업 시

- 접속: VS Code Remote - SSH, 호스트 `rpi5` (`~/.ssh/config`에 정의). IP가 바뀌면 `hostname -I`로 확인 후 config의 `HostName`만 수정.
- Pi 환경: Raspberry Pi OS Trixie(64-bit), Python 3.13.5(시스템), HailoRT 4.23.0, `hailo-all` 5.1.1, TAPPAS core 5.1.0, Hailo Apps `~/hailo-apps`.
- 원격 접속: Tailscale 1.104.4가 호스트에 apt 패키지로 설치됨(`tailscaled` 상시 실행, Docker 아님). tailnet 이름 `npu-03`, IP `100.119.172.74`. Tailscale SSH·서브넷 라우팅·exit node·serve는 꺼져 있다. 원격 접속 경로이므로 Docker로 옮기거나 `tailscaled`를 중지·재설정하지 않는다(필요하면 먼저 사용자 확인). 상세는 `README.md` 3-8.
- `npu_setup.sh`는 일반 사용자로 `bash ~/npu_setup.sh {1|2|3}` 형태로 실행한다. `sudo bash`로 실행하지 않는다.
- 이미 3단계 설치가 끝난 장비에서는 설치 스크립트를 재실행하지 않고 `npu_check*.sh`만 사용한다.
- `[PASS]`는 명령/파일/장치 확인 통과일 뿐이며, 영상 품질·탐지 결과는 사람이 직접 확인해야 한다.
- numpy 버전이 환경마다 다르다(시스템 2.2.4 / `venv_hailo_apps` 1.26.4). 시스템 파이썬에 패키지를 임의 설치하지 않는다.

## 검증

- 결과를 사용자에게 보여주기 전에 에이전트가 먼저 확인한다. 무엇을 어떤 방법으로 확인했고, 확인하지 못한 것이 무엇인지 구분해서 보고한다.
- PC 코드 변경 후 최소한 `python day1\test.py`로 인터프리터·패키지가 정상인지 확인한다.
- Pi 스크립트를 수정하면 `bash -n`으로 구문 검사를 한다.
- 실행 환경이 없어 동작 확인이 불가능하면 가능한 검증(문법 검사 등)까지만 하고 나머지는 "미확인"으로 적는다.
- lint/typecheck/test 설정은 아직 없다. 새로 도입하면 이 문서에 명령을 추가한다.
