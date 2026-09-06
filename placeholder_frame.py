"""Generates a simple placeholder frame image so the pipeline is testable
without a real frame.png (a plain wall + a wooden-looking rectangle border
around the aperture)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def generate_placeholder_frame(aperture: dict, border: int = 60, margin: int = 200) -> Image.Image:
    x, y, w, h = aperture["x"], aperture["y"], aperture["width"], aperture["height"]
    canvas_w = x + w + margin
    canvas_h = y + h + margin

    img = Image.new("RGB", (canvas_w, canvas_h), (233, 229, 222))  # wall color
    draw = ImageDraw.Draw(img)

    # wooden frame border around the aperture
    draw.rectangle(
        [x - border, y - border, x + w + border, y + h + border],
        fill=(92, 60, 36),
        outline=(60, 38, 22),
        width=4,
    )
    # inner bevel highlight
    draw.rectangle(
        [x - border // 3, y - border // 3, x + w + border // 3, y + h + border // 3],
        outline=(140, 100, 66),
        width=3,
    )
    # aperture itself, left as flat mid-gray to signal "empty slot"
    draw.rectangle([x, y, x + w, y + h], fill=(210, 210, 210))

    return img


def ensure_frame_exists(frame_path: Path, aperture: dict) -> None:
    if frame_path.exists():
        return
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    placeholder = generate_placeholder_frame(aperture)
    placeholder.save(frame_path)
