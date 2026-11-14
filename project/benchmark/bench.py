#!/usr/bin/env python3
"""Run the same video frames through ONNX (CPU) and HEF (NPU) and compare latency.

Designed to run inside the Frigate image, which already has onnxruntime,
opencv, numpy and hailo_platform. The NPU path needs exclusive access to
/dev/hailo0, so stop Frigate before running it.
"""

import argparse
import json
import statistics
import time

import cv2
import numpy as np

PAD_VALUE = 114
SCORE_THRESHOLD = 0.4


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--clip", required=True, help="input video path")
    p.add_argument("--onnx", required=True, help="YOLOv6 ONNX model path")
    p.add_argument("--hef", required=True, help="YOLOv6 HEF model path")
    p.add_argument("--frames", type=int, default=60, help="frames sampled from the clip")
    p.add_argument("--warmup", type=int, default=10, help="warmup inferences per backend")
    p.add_argument("--repeat", type=int, default=3, help="passes over the sampled frames")
    p.add_argument("--threads", type=int, default=0, help="ONNX intra-op threads (0 = runtime default)")
    p.add_argument("--only", choices=["both", "cpu", "npu"], default="both")
    p.add_argument("--json", help="write results to this JSON path")
    return p.parse_args()


def load_frames(path, count):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise SystemExit(f"cannot open clip: {path}")
    frames = []
    while len(frames) < count:
        ok, frame = cap.read()
        if not ok:
            if not frames:
                raise SystemExit(f"no decodable frames in clip: {path}")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
            if not ok:
                break
        frames.append(frame)
    cap.release()
    return frames


def letterbox_rgb(frame, height, width):
    h, w = frame.shape[:2]
    scale = min(width / w, height / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    canvas = np.full((height, width, 3), PAD_VALUE, dtype=frame.dtype)
    x = (width - new_w) // 2
    y = (height - new_h) // 2
    canvas[y : y + new_h, x : x + new_w] = resized
    return cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)


def stats_ms(samples):
    return {
        "n": len(samples),
        "mean_ms": statistics.fmean(samples),
        "median_ms": statistics.median(samples),
        "p95_ms": float(np.percentile(samples, 95)),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "fps": 1000.0 / statistics.fmean(samples),
    }


def count_onnx_detections(output):
    pred = np.squeeze(output)
    if pred.shape[0] < pred.shape[1]:
        pred = pred.T
    scores = pred[:, 4] * pred[:, 5:].max(axis=1)
    return int((scores > SCORE_THRESHOLD).sum())


def count_npu_detections(outputs):
    total = 0
    for arr in outputs.values():
        if arr is None or arr.size == 0:
            continue
        if arr.ndim == 3:
            total += int((arr[:, 4, :] > SCORE_THRESHOLD).sum())
        elif arr.ndim == 2:
            total += int((arr[:, 4] > SCORE_THRESHOLD).sum())
    return total


def preprocess(frame, height, width):
    rgb = letterbox_rgb(frame, height, width)
    nchw = np.expand_dims(rgb.astype(np.float32).transpose(2, 0, 1) / 255.0, 0)
    nhwc = np.expand_dims(rgb, 0)
    return nchw, nhwc


def bench_cpu(args, frames):
    import onnxruntime as ort

    options = ort.SessionOptions()
    if args.threads > 0:
        options.intra_op_num_threads = args.threads
    session = ort.InferenceSession(
        args.onnx, sess_options=options, providers=["CPUExecutionProvider"]
    )
    input_meta = session.get_inputs()[0]
    input_name = input_meta.name
    model_h, model_w = int(input_meta.shape[2]), int(input_meta.shape[3])

    tensors = [preprocess(f, model_h, model_w)[0] for f in frames[: args.warmup]]
    for tensor in tensors:
        session.run(None, {input_name: tensor})

    infer_ms = []
    pre_ms = []
    detections = []
    for _ in range(args.repeat):
        for frame in frames:
            t0 = time.perf_counter()
            nchw, _ = preprocess(frame, model_h, model_w)
            pre_ms.append((time.perf_counter() - t0) * 1000.0)

            t0 = time.perf_counter()
            out = session.run(None, {input_name: nchw})[0]
            infer_ms.append((time.perf_counter() - t0) * 1000.0)
            detections.append(count_onnx_detections(out))

    result = stats_ms(infer_ms)
    result["preprocess_mean_ms"] = statistics.fmean(pre_ms)
    result["detections_mean"] = statistics.fmean(detections)
    result["input_shape"] = [model_h, model_w, 3]
    return result


def bench_npu(args, frames):
    from hailo_platform import (
        HEF,
        ConfigureParams,
        FormatType,
        HailoStreamInterface,
        InferVStreams,
        InputVStreamParams,
        OutputVStreamParams,
        VDevice,
    )

    hef = HEF(args.hef)
    input_info = hef.get_input_vstream_infos()[0]
    input_name = input_info.name
    out_height, out_width = int(input_info.shape[0]), int(input_info.shape[1])

    target = VDevice()
    try:
        configure_params = ConfigureParams.create_from_hef(
            hef, interface=HailoStreamInterface.PCIe
        )
        network_group = target.configure(hef, configure_params)[0]
        input_params = InputVStreamParams.make(
            network_group, quantized=False, format_type=FormatType.UINT8
        )
        output_params = OutputVStreamParams.make(
            network_group, quantized=False, format_type=FormatType.FLOAT32
        )

        with InferVStreams(network_group, input_params, output_params) as pipeline:
            with network_group.activate(network_group.create_params()):
                for frame in frames[: args.warmup]:
                    _, nhwc = preprocess(frame, out_height, out_width)
                    pipeline.infer({input_name: nhwc})

                infer_ms = []
                pre_ms = []
                detections = []
                for _ in range(args.repeat):
                    for frame in frames:
                        t0 = time.perf_counter()
                        _, nhwc = preprocess(frame, out_height, out_width)
                        pre_ms.append((time.perf_counter() - t0) * 1000.0)

                        t0 = time.perf_counter()
                        outputs = pipeline.infer({input_name: nhwc})
                        infer_ms.append((time.perf_counter() - t0) * 1000.0)
                        detections.append(count_npu_detections(outputs))

        result = stats_ms(infer_ms)
        result["preprocess_mean_ms"] = statistics.fmean(pre_ms)
        result["detections_mean"] = statistics.fmean(detections)
        result["input_shape"] = [out_height, out_width, 3]
        return result
    finally:
        target.release()


def print_row(name, result):
    print(
        f"{name:<4} n={result['n']:<5} "
        f"infer mean={result['mean_ms']:8.2f} ms  "
        f"median={result['median_ms']:8.2f}  p95={result['p95_ms']:8.2f}  "
        f"fps={result['fps']:7.2f}  "
        f"pre={result['preprocess_mean_ms']:6.2f} ms  "
        f"det={result['detections_mean']:5.1f}"
    )


def main():
    args = parse_args()

    frames = load_frames(args.clip, args.frames)
    height, width = frames[0].shape[:2]
    print(f"clip={args.clip} frames={len(frames)} source={width}x{height} repeat={args.repeat}")

    results = {
        "clip": args.clip,
        "frames": len(frames),
        "repeat": args.repeat,
        "source_width": width,
        "source_height": height,
    }

    if args.only in ("both", "cpu"):
        results["cpu"] = bench_cpu(args, frames)
        print_row("cpu", results["cpu"])

    if args.only in ("both", "npu"):
        results["npu"] = bench_npu(args, frames)
        print_row("npu", results["npu"])

    if "cpu" in results and "npu" in results:
        speedup = results["cpu"]["mean_ms"] / results["npu"]["mean_ms"]
        print(f"speedup: NPU is {speedup:.2f}x faster (inference only)")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
