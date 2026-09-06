"""Composites an artwork into the frame's aperture using Pillow."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter


def _fit_cover(artwork_img: Image.Image, width: int, height: int) -> Image.Image:
    """Scale to fill the target box completely, cropping the overflow."""
    src_ratio = artwork_img.width / artwork_img.height
    dst_ratio = width / height

    if src_ratio > dst_ratio:
        # source is relatively wider -> match height, crop left/right
        new_height = height
        new_width = round(height * src_ratio)
    else:
        new_width = width
        new_height = round(width / src_ratio)

    resized = artwork_img.resize((new_width, new_height), Image.LANCZOS)
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _fit_contain(
    artwork_img: Image.Image, width: int, height: int, passepartout_color: tuple
) -> Image.Image:
    """Scale to fit entirely inside the target box, padding with a solid color."""
    src_ratio = artwork_img.width / artwork_img.height
    dst_ratio = width / height

    if src_ratio > dst_ratio:
        new_width = width
        new_height = round(width / src_ratio)
    else:
        new_height = height
        new_width = round(height * src_ratio)

    resized = artwork_img.resize((new_width, new_height), Image.LANCZOS)
    canvas = Image.new("RGB", (width, height), tuple(passepartout_color))
    offset = ((width - new_width) // 2, (height - new_height) // 2)
    canvas.paste(resized, offset)
    return canvas


def _apply_drop_shadow(frame: Image.Image, aperture: dict, blur: int = 12, offset: int = 4) -> Image.Image:
    """Darken a soft band just outside the aperture edge for a recessed look."""
    shadow_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow_layer)
    x, y, w, h = aperture["x"], aperture["y"], aperture["width"], aperture["height"]
    draw.rectangle(
        [x - offset, y - offset, x + w + offset, y + h + offset],
        outline=(0, 0, 0, 160),
        width=offset * 2,
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(frame.convert("RGBA"), shadow_layer)


def _apply_vignette(inset_img: Image.Image, strength: int = 90) -> Image.Image:
    """Cheap glass-reflection-ish vignette: subtly darken the corners."""
    w, h = inset_img.size
    vignette = Image.new("L", (w, h), 255 - strength)
    draw = ImageDraw.Draw(vignette)
    margin = int(min(w, h) * 0.35)
    draw.ellipse([-margin, -margin, w + margin, h + margin], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(min(w, h) * 0.2))

    dark = Image.new("RGB", (w, h), (20, 20, 20))
    return Image.composite(inset_img, dark, vignette)


def compose(
    frame_img: Image.Image,
    artwork_img: Image.Image,
    aperture: dict,
    fit_mode: str,
    passepartout_color: tuple,
    drop_shadow: bool = True,
    vignette: bool = True,
) -> Image.Image:
    """Return a new image with the artwork composited into the frame's aperture."""
    x, y, w, h = aperture["x"], aperture["y"], aperture["width"], aperture["height"]

    if fit_mode == "contain":
        inset = _fit_contain(artwork_img, w, h, passepartout_color)
    else:
        inset = _fit_cover(artwork_img, w, h)

    if vignette:
        inset = _apply_vignette(inset)

    result = frame_img.convert("RGBA").copy()
    result.paste(inset, (x, y))

    if drop_shadow:
        result = _apply_drop_shadow(result, aperture)

    return result.convert("RGB")
