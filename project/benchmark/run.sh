#!/usr/bin/env bash
# Stop Frigate (NPU is exclusive), run the CPU/NPU benchmark in the Frigate image,
# then start Frigate again. Without --yes only the CPU run is executed.
set -euo pipefail

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRIGATE_DIR="${BENCH_DIR}/../docker/frigate"
MODEL_DIR="${BENCH_DIR}/models"
CLIP_DIR="${BENCH_DIR}/clips"
RESULT_DIR="${BENCH_DIR}/results"
IMAGE="${IMAGE:-localhost/frigate-hailort4.23:0.18.2}"

CLIP="${CLIP:-$(find "${CLIP_DIR}" -maxdepth 1 -name '*.mp4' | sort | tail -1)}"
ONNX="${ONNX:-${MODEL_DIR}/yolov6n.onnx}"
HEF="${HEF:-${MODEL_DIR}/yolov6n.hef}"

STOP_FRIGATE=0
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes) STOP_FRIGATE=1; shift ;;
        --frames|--repeat|--warmup)
            EXTRA_ARGS+=("$1" "$2"); shift 2 ;;
        *) echo "usage: $0 [--yes] [--frames N] [--repeat N] [--warmup N]" >&2; exit 1 ;;
    esac
done

if [[ -z "${CLIP}" || ! -f "${CLIP}" ]]; then
    echo "No clip found. Capture one first: ${BENCH_DIR}/capture_clip.sh" >&2
    exit 1
fi
if [[ ! -f "${ONNX}" || ! -f "${HEF}" ]]; then
    echo "Missing model files. Run ${BENCH_DIR}/fetch_models.sh first." >&2
    exit 1
fi

mkdir -p "${RESULT_DIR}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RESULT_JSON="/results/bench_${STAMP}.json"
ONLY="both"

if [[ "${STOP_FRIGATE}" -eq 1 ]]; then
    echo "Stopping Frigate to free /dev/hailo0..."
    docker compose -f "${FRIGATE_DIR}/compose.yaml" stop frigate
    trap 'echo "Starting Frigate..."; docker compose -f "${FRIGATE_DIR}/compose.yaml" start frigate' EXIT
else
    echo "Frigate is still running, so only the CPU run is executed."
    echo "Re-run with --yes to stop Frigate temporarily and include the NPU run."
    ONLY="cpu"
fi

docker run --rm \
    --user "$(id -u):$(id -g)" \
    --device /dev/hailo0 \
    -v "${BENCH_DIR}:/bench:ro" \
    -v "$(dirname "${CLIP}")":/clips:ro \
    -v "${MODEL_DIR}":/models:ro \
    -v "${RESULT_DIR}":/results \
    --entrypoint python3 \
    "${IMAGE}" /bench/bench.py \
    --clip "/clips/$(basename "${CLIP}")" \
    --onnx "/models/$(basename "${ONNX}")" \
    --hef "/models/$(basename "${HEF}")" \
    --only "${ONLY}" \
    "${EXTRA_ARGS[@]}" \
    --json "${RESULT_JSON}"

echo "Result: ${RESULT_DIR}/bench_${STAMP}.json"
