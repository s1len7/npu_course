from pathlib import Path
import torch
from torchvision.models import(
    mobilenet_v2,
    MobileNet_V2_Weights
)

OUTPUT_FILE = Path("../output/mobilenet_v2.onnx")

weights = MobileNet_V2_Weights.DEFAULT
model = mobilenet_v2(weights=weights)

model.eval()

dummy_input = torch.randn(
    1, 3, 224, 224, dtype=torch.float32
)

torch.onnx.export(
    model,
    (dummy_input, ),
    str(OUTPUT_FILE),
    input_names=["input"],
    output_names=["output"],
    dynamo=True,
    external_data=False
)

print("ONNX Export 완료")
print(f"저장 경로: {OUTPUT_FILE}")










