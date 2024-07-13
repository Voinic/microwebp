# MicroWEBP
WEBP decoder for MicroPython devices written in pure Python

Code translated from https://sourceforge.net/projects/javavp8decoder/

## Installation using MIP:
```python
import mip
mip.install("github:Voinic/microwebp")
```

## Usage:
```python
from uwebp import WebPReader

with open("image.webp", "rb") as f:
    reader = WebPReader(f)
    image = reader.read()
```
