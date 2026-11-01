import torch
from torchvision.models import mobilenet_v2, MobileNet_V2_Weights

weights = MobileNet_V2_Weights.DEFAULT
print(weights)

model = mobilenet_v2(weights=weights)
model.eval()

print(model.__class__.__name__)

device = torch.device("cpu")
print("사용 Device: ", device)
print(f"CUDA 사용 가능: {torch.cuda.is_available()}")