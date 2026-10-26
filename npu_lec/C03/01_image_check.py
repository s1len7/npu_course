from PIL import Image
from pathlib import Path

image_path = Path("./C03/images/red_square.jpg")

print(f"Checking image at: {image_path}")
print(f"Image exists: {image_path.exists()}")

image = Image.open(image_path)
print(f"Image format: {image.format}")
print(f"Image size: {image.size}")
print(f"Image mode: {image.mode}")


image2 = Image.open(image_path).convert("RGB")

import numpy as np

array = np.array(image2)
print(f"Image array shape: {array.shape}")
print(f"Image array dtype: {array.dtype}")
print(f"Image array.max(): {array.max()}, array.min(): {array.min()}")


