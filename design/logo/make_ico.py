"""Packs src/site/brand/favicon-16/32/48.png into favicon.ico, for browsers that ask for /favicon.ico (SI-9)."""
from pathlib import Path
from PIL import Image

d = Path(__file__).resolve().parents[2] / "src" / "site" / "brand"
imgs = [Image.open(d / f"favicon-{s}.png").convert("RGBA") for s in (16, 32, 48)]
imgs[2].save(d / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=imgs[:2])
