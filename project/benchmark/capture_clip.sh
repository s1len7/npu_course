#!/usr/bin/env bash
# Save a fixed reference clip from the live camera through MediaMTX.
set -euo pipefail

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIP_DIR="${BENCH_DIR}/clips"
SOURCE="rtsp://127.0.0.1:8564/cam"
DURATION=120
OUTPUT=""

usage() {
    echo "usage: $0 [-s rtsp_url] [-d seconds] [-o output.mp4]" >&2
}

while getopts "s:d:o:h" opt; do
    case "${opt}" in
        s) SOURCE="${OPTARG}" ;;
        d) DURATION="${OPTARG}" ;;
        o) OUTPUT="${OPTARG}" ;;
        *) usage; exit 1 ;;
    esac
done

mkdir -p "${CLIP_DIR}"
if [[ -z "${OUTPUT}" ]]; then
    OUTPUT="${CLIP_DIR}/cam_$(date +%Y%m%d_%H%M%S).mp4"
fi

echo "Capturing ${DURATION}s from ${SOURCE} -> ${OUTPUT}"
ffmpeg -hide_banner -loglevel warning -rtsp_transport tcp \
    -i "${SOURCE}" -t "${DURATION}" -c copy -y "${OUTPUT}"
echo "Saved ${OUTPUT}"
