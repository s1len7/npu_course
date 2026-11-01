import torch
from PIL import Image
from torchvision.models import mobilenet_v2, MobileNet_V2_Weights


weights = MobileNet_V2_Weights.DEFAULT
print(weights)

preprocessor = weights.transforms()

image_path = "../C04_data/images/cat.jpg"
image = Image.open(image_path).convert("RGB")

tensor = preprocessor(image)

print("Tensor shape: ", tensor.shape)
print("Tensor dtype: ", tensor.dtype)
print("Tensor min: ", tensor.min().item())
print("Tensor max: ", tensor.max().item())

print()
input_batch = tensor.unsqueeze(0)
print("input_batch shape: ", input_batch.shape)

model = mobilenet_v2(weights=weights)
model.eval()

with torch.no_grad():
    output = model(input_batch)

print("output shape: ", output.shape)
print(f"\nresult:\n{output}")


probabilities = torch.softmax(
    output[0],
    dim=0
)

print(probabilities)

top1_index = probabilities.argmax().item()
print("top-1 index : ", top1_index)

top1_score = probabilities[top1_index].item()
print("top-1 score : ", top1_score)

categories = weights.meta["categories"]
print("categories : ", categories)

top1_name = categories[top1_index]
print("top-1 name : ", top1_name)







