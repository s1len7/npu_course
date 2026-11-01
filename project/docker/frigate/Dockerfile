# syntax=docker/dockerfile:1.7
#
# Frigate v0.18.2 이미지의 HailoRT 사용자 영역을 4.21.0 → 4.23.0으로 교체한다.
# 호스트 드라이버(hailo_pci 4.23.0, hailo-all 5.1.1)는 건드리지 않고, 라이브러리를 드라이버 버전에 맞춘다.
# HailoRT는 드라이버와 라이브러리 버전이 major.minor.revision까지 같아야 동작한다.
#
# 근거·미확인 항목: ../../AGENTS.md §3
# 교체 파일 출처: https://github.com/frigate-nvr/hailort/releases/tag/v4.23.0 (Frigate 팀 빌드)

ARG FRIGATE_VERSION=0.18.2

# NPU를 다른 프로세스(Hailo Whisper STT)와 함께 쓰려면 HailoRT 멀티프로세스 서비스 지원이 필요하다.
# Frigate 팀 빌드는 HAILO_BUILD_SERVICE=OFF라 libhailort.so만 같은 버전 소스로 다시 빌드한다.
# (Frigate 이미지와 같은 Debian 12 기준, Python 바인딩은 libhailort.so를 동적 링크하므로 그대로 둔다)
FROM debian:12 AS hailort-service-build
ARG DEBIAN_FRONTEND=noninteractive
ARG HAILORT_VERSION=4.23.0
RUN apt-get -qq update \
    && apt-get -qq install -y build-essential cmake git wget pkg-config >/dev/null \
    && rm -rf /var/lib/apt/lists/*
RUN git clone -q --depth 1 --branch "v${HAILORT_VERSION}" https://github.com/hailo-ai/hailort.git /source \
    && cd /source \
    && cmake -H. -Bbuild -DCMAKE_BUILD_TYPE=Release -DHAILO_BUILD_SERVICE=1 \
    && cmake --build build -j "$(nproc)" --config release --target libhailort \
    && mkdir -p /out \
    && cp -a build/hailort/libhailort/src/libhailort.so* /out/

# standard: Frigate 팀 HailoRT 4.23.0 (NPU 단독 사용)
FROM ghcr.io/blakeblackshear/frigate:${FRIGATE_VERSION} AS standard

# Frigate 원본 Dockerfile과 같은 방식으로 PEP 668(시스템 Python 보호) 제약을 빌드 중에만 해제
ARG PIP_BREAK_SYSTEM_PACKAGES=1
ARG HAILORT_VERSION=4.23.0
ARG HAILORT_RELEASE=https://github.com/frigate-nvr/hailort/releases/download/v${HAILORT_VERSION}

# 체크섬은 2026-11-01에 릴리스 파일을 내려받아 계산한 값
ADD --checksum=sha256:e91a492d0765b22f1030479d4fca800cfdd87c8f1f93ad427e0c877ad96979ad \
    ${HAILORT_RELEASE}/hailort-debian12-arm64.tar.gz /tmp/hailort.tar.gz
ADD --checksum=sha256:19caae31178593000437dd14e421dd3421bb0315b96134b5d024362df91638f9 \
    ${HAILORT_RELEASE}/hailort-${HAILORT_VERSION}-cp311-cp311-linux_aarch64.whl \
    /tmp/hailort-${HAILORT_VERSION}-cp311-cp311-linux_aarch64.whl

# tar 구조: rootfs/usr/local/{bin/hailortcli, lib/libhailort.so*}
# 기존 4.21 라이브러리를 지우고 4.23으로 덮어쓴 뒤 Python 바인딩(_pyhailort)도 같은 버전으로 교체
RUN set -eux; \
    rm -f /usr/local/lib/libhailort.so.*; \
    tar -xzf /tmp/hailort.tar.gz -C / --strip-components=1; \
    ldconfig; \
    pip3 install --no-cache-dir --force-reinstall --no-deps \
        /tmp/hailort-${HAILORT_VERSION}-cp311-cp311-linux_aarch64.whl; \
    rm -f /tmp/hailort.tar.gz /tmp/hailort-*.whl; \
    test -f "/usr/local/lib/libhailort.so.${HAILORT_VERSION}"; \
    test "$(pip3 show hailort | sed -n 's/^Version: //p')" = "${HAILORT_VERSION}"

# service: standard + 멀티프로세스 서비스 지원 libhailort.so (NPU를 Hailo Whisper STT와 공유)
FROM standard AS service

# 멀티프로세스 서비스 지원 libhailort.so로 교체하고, Frigate 감지기가 서비스 경유로 NPU를 쓰게 한다.
# 서비스 소켓(/tmp/hailort_uds.sock)은 compose에서 호스트 hailort.service(4.23.0) 것을 마운트한다.
COPY --from=hailort-service-build /out/ /usr/local/lib/
RUN set -eux; \
    ldconfig; \
    f=/opt/frigate/frigate/detectors/plugins/hailo8l.py; \
    sed -i 's/^\( *\)params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN$/&\n\1params.multi_process_service = True\n\1params.group_id = "SHARED"/' "$f"; \
    grep -q 'params.multi_process_service = True' "$f"
