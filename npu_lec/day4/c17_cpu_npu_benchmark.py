from pathlib import Path

import cv2
import numpy as np

from hailo_platform import (
    HEF,
    VDevice,
    ConfigureParams,
    HailoStreamInterface,
    InputVStreamParams,
    OutputVStreamParams,
    InferVStreams,
    FormatType,
)


# ---------------------------------------------------------
# 1. 파일 경로
# ---------------------------------------------------------

WORK_DIR = Path.home() / "hailo_models"
C17_DIR = WORK_DIR / "c17"

HEF_PATH = WORK_DIR / "mobilenet_v1.hef"
IMAGE_PATH = C17_DIR / "input.jpg"
RESULT_PATH = C17_DIR / "c17_top5.csv"


# ---------------------------------------------------------
# 2. 파일 존재 확인
# ---------------------------------------------------------

if not HEF_PATH.exists():
    raise FileNotFoundError(f"HEF 파일 없음: {HEF_PATH}")

if not IMAGE_PATH.exists():
    raise FileNotFoundError(f"입력 이미지 없음: {IMAGE_PATH}")


print("[HEF]")
print(HEF_PATH)

print("\n[IMAGE]")
print(IMAGE_PATH)


# ---------------------------------------------------------
# 3. HEF 로드
# ---------------------------------------------------------

hef = HEF(str(HEF_PATH))

input_info = hef.get_input_vstream_infos()[0]
output_info = hef.get_output_vstream_infos()[0]

print("\n[HEF INPUT]")
print("name :", input_info.name)
print("shape:", input_info.shape)

print("\n[HEF OUTPUT]")
print("name :", output_info.name)
print("shape:", output_info.shape)


# ---------------------------------------------------------
# 4. HEF 입력 크기 확인
# ---------------------------------------------------------

input_height, input_width, input_channels = input_info.shape

print("\n[INPUT SIZE]")
print("height  :", input_height)
print("width   :", input_width)
print("channels:", input_channels)


# ---------------------------------------------------------
# 5. 실제 JPEG 읽기
# ---------------------------------------------------------

image_bgr = cv2.imread(str(IMAGE_PATH))

if image_bgr is None:
    raise RuntimeError(f"이미지를 읽지 못했습니다: {IMAGE_PATH}")

print("\n[ORIGINAL IMAGE]")
print("shape:", image_bgr.shape)
print("dtype:", image_bgr.dtype)


# ---------------------------------------------------------
# 6. BGR → RGB
# ---------------------------------------------------------

image_rgb = cv2.cvtColor(
    image_bgr,
    cv2.COLOR_BGR2RGB
)


# ---------------------------------------------------------
# 7. 모델 입력 크기로 Resize
# ---------------------------------------------------------

resized = cv2.resize(
    image_rgb,
    (input_width, input_height)
)

print("\n[RESIZED IMAGE]")
print("shape:", resized.shape)
print("dtype:", resized.dtype)
print("min  :", resized.min())
print("max  :", resized.max())


# ---------------------------------------------------------
# 8. Batch 차원 추가
#
# HWC
# (224, 224, 3)
#
# ↓
#
# NHWC
# (1, 224, 224, 3)
# ---------------------------------------------------------

input_tensor = np.expand_dims(
    resized,
    axis=0
).astype(np.uint8)

print("\n[INPUT TENSOR]")
print("shape:", input_tensor.shape)
print("dtype:", input_tensor.dtype)


# ---------------------------------------------------------
# 9. Hailo Virtual Device 생성
# ---------------------------------------------------------

with VDevice() as target:

    # HEF 기준 장치 설정
    configure_params = ConfigureParams.create_from_hef(
        hef=hef,
        interface=HailoStreamInterface.PCIe,
    )

    network_groups = target.configure(
        hef,
        configure_params,
    )

    network_group = network_groups[0]

    network_group_params = network_group.create_params()


    # -----------------------------------------------------
    # 10. 입력 / 출력 VStream 설정
    #
    # 입력:
    # RGB uint8 이미지
    #
    # 출력:
    # Top-K 계산이 쉽도록 float32
    # -----------------------------------------------------

    input_vstreams_params = InputVStreamParams.make(
        network_group,
        format_type=FormatType.UINT8,
    )

    output_vstreams_params = OutputVStreamParams.make(
        network_group,
        format_type=FormatType.FLOAT32,
    )


    input_data = {
        input_info.name: input_tensor
    }


    # -----------------------------------------------------
    # 11. 실제 Hailo-8L 추론
    # -----------------------------------------------------

    with InferVStreams(
        network_group,
        input_vstreams_params,
        output_vstreams_params,
    ) as infer_pipeline:

        with network_group.activate(
            network_group_params
        ):

            infer_results = infer_pipeline.infer(
                input_data
            )


# ---------------------------------------------------------
# 12. Output Tensor 가져오기
# ---------------------------------------------------------

output_tensor = infer_results[
    output_info.name
]

print("\n[RAW OUTPUT]")
print("shape:", output_tensor.shape)
print("dtype:", output_tensor.dtype)


# ---------------------------------------------------------
# 13. 1차원 Class Score로 변환
# ---------------------------------------------------------

scores = np.asarray(
    output_tensor
).reshape(-1)

print("\n[CLASS SCORES]")
print("number of scores:", len(scores))
print("score min       :", scores.min())
print("score max       :", scores.max())
print("score sum       :", scores.sum())


# ---------------------------------------------------------
# 14. Top-5
# ---------------------------------------------------------

top5_indices = np.argsort(
    scores
)[-5:][::-1]


print("\n==============================")
print("TOP-5 CLASSIFICATION")
print("==============================")

rows = []

for rank, output_index in enumerate(
    top5_indices,
    start=1,
):

    score = float(
        scores[output_index]
    )

    # mobilenet_v1 Model Zoo output은 1001개이며
    # ImageNet label에는 offset 1이 적용된다.
    #
    # output 0 = background/offset 영역
    # output 1 = ImageNet class 0
    # ...
    # output 1000 = ImageNet class 999

    imagenet_index = (
        output_index - 1
        if output_index > 0
        else -1
    )

    print(
        f"TOP-{rank}: "
        f"output_index={output_index}, "
        f"imagenet_index={imagenet_index}, "
        f"score={score:.6f}"
    )

    rows.append(
        (
            rank,
            int(output_index),
            int(imagenet_index),
            score,
        )
    )


# ---------------------------------------------------------
# 15. CSV 저장
# ---------------------------------------------------------

with open(
    RESULT_PATH,
    "w",
    encoding="utf-8",
) as f:

    f.write(
        "rank,output_index,"
        "imagenet_index,score\n"
    )

    for row in rows:
        f.write(
            f"{row[0]},"
            f"{row[1]},"
            f"{row[2]},"
            f"{row[3]:.8f}\n"
        )


print("\n[RESULT SAVED]")
print(RESULT_PATH)