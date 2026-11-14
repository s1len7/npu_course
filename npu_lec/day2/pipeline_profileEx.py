import csv
import statistics

from PIL import Image
import torch
from torchvision.models import mobilenet_v2, MobileNet_V2_Weights
import time
from pathlib import Path


WARMUP = 10
ITERATIONS = 100
IMAGE_PATH = "../../C04/C04_data/images/cat.jpg"

device = torch.device("cpu")
weigths = MobileNet_V2_Weights.DEFAULT
preprocess = weigths.transforms()
model = mobilenet_v2(weights=weigths).to(device)
model.eval()

warm_image = Image.open("../../C04/C04_data/images/horse.jpg").convert("RGB")
warm_input = preprocess(warm_image).unsqueeze(0).to(device)

with torch.inference_mode():
    for _ in range(WARMUP):
        _ = model(warm_input)

# Stage 결과 저장
load_times = []
preprocess_times = []
inference_times = []
postprocess_times = []
total_times = []

#pipeline benchmark

for _ in range(ITERATIONS):
    total_start = time.perf_counter()

    #image loading
    start = time.perf_counter()
    image = Image.open(IMAGE_PATH).convert("RGB")
    end = time.perf_counter()
    load_times.append((end - start) * 1000)

    # preprocessing
    start = time.perf_counter()
    input_batch = preprocess(image).unsqueeze(0).to(device)
    end = time.perf_counter()
    preprocess_times.append((end - start) * 1000)

    #inference
    start = time.perf_counter()
    with torch.inference_mode():
        output = model(input_batch)
    end = time.perf_counter()
    inference_times.append((end - start) * 1000)


    #postprocessing
    start = time.perf_counter()
    probabilities = torch.softmax(
        output[0],
        dim=0
    )

    top5_prob, top5_idx = torch.topk(probabilities, 5)
    end = time.perf_counter()
    postprocess_times.append((end - start) * 1000)

    total_end = time.perf_counter()
    total_times.append((total_end - total_start) * 1000)

print("\n===== RESULTS =====")
print(f"Load times: {statistics.mean(load_times):.3f} ms")
print(f"Preprocess times: {statistics.mean(preprocess_times):.3f} ms")
print(f"Inference times: {statistics.mean(inference_times):.3f} ms")
print(f"Postprocess times: {statistics.mean(postprocess_times):.3f} ms")
print(f"Total times: {statistics.mean(total_times):.3f} ms")
