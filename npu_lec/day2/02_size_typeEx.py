from PIL import Image
import numpy as np

image = Image.open('../output/red_square_224.jpg').convert('RGB')
image = image.resize((224, 224))

array = np.array(image)
print(array.shape)

chw = np.transpose(array,(2,0,1))

print("변환 shape:", chw.shape)

print("변환전 dtype: ", array.dtype)

array = array.astype(np.float32)
print("변환 후 dtype: ", array.dtype)
print(f"데이터 범위: {array.min()} ~ {array.max()}")

array = array / 255.

print(f"변환 후 데이터 범위: {array.min()} ~ {array.max()}")

tdata = array.copy().transpose((2,0,1))

import torch

tensor = torch.from_numpy(tdata)

print()
print(f"Tensor shape: {tensor.shape}")
print(f"Tensor dtype: {tensor.dtype}")
print(f"Tensor min: {tensor.min()}, max: {tensor.max()}")














