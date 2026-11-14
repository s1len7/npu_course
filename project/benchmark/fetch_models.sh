#!/usr/bin/env bash
# Fetch the YOLOv6n ONNX (CPU run) and HEF (NPU run) used by Frigate.
set -euo pipefail

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="${BENCH_DIR}/models"
FRIGATE_CACHE="${BENCH_DIR}/../docker/frigate/config/model_cache"

ONNX_ZIP_URL="https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ObjectDetection/Detection-COCO/yolo/yolov6n/pretrained/2023-05-31/yolov6n.zip"
HEF_URL="https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.14.0/hailo8l/yolov6n.hef"

mkdir -p "${MODEL_DIR}"

if [[ ! -f "${MODEL_DIR}/yolov6n.onnx" ]]; then
    echo "Downloading YOLOv6n ONNX source..."
    tmp_zip="${MODEL_DIR}/yolov6n.zip"
    curl -fL --retry 3 -o "${tmp_zip}" "${ONNX_ZIP_URL}"
    unzip -o -j "${tmp_zip}" yolov6n.onnx -d "${MODEL_DIR}" >/dev/null
    rm -f "${tmp_zip}"
fi
echo "ONNX: ${MODEL_DIR}/yolov6n.onnx"

if [[ ! -f "${MODEL_DIR}/yolov6n.hef" ]]; then
    if [[ -f "${FRIGATE_CACHE}/yolov6n.hef" ]]; then
        echo "Copying HEF from Frigate model cache..."
        cp "${FRIGATE_CACHE}/yolov6n.hef" "${MODEL_DIR}/yolov6n.hef"
    else
        echo "Downloading HEF..."
        curl -fL --retry 3 -o "${MODEL_DIR}/yolov6n.hef" "${HEF_URL}"
    fi
fi
echo "HEF : ${MODEL_DIR}/yolov6n.hef"
