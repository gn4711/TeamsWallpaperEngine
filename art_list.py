"""Loads the static curated list of classic public-domain paintings
(art_list.json, generated ahead of time by build_art_list.py from Wikidata)
and downloads the chosen artwork's image.

No live API querying happens here - the list is already filtered to real,
verified, colorful, 200+ year old classics, so picking one at runtime is a
purely local, instant operation. Only the final chosen image gets downloaded.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass
class Artwork:
    id: str
    title: str
    artist: str
    year: int
    sitelinks: int
    image_url: str
    aspect_ratio: Optional[float] = None  # from physical dimensions; may be unknown


class ArtListError(Exception):
    pass


def load_art_list(path: Path) -> list[Artwork]:
    if not path.exists():
        raise ArtListError(
            f"{path} not found. Run `python build_art_list.py` to generate it."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtListError(f"{path} is not valid JSON: {exc}") from exc

    if not raw:
        raise ArtListError(f"{path} is empty.")

    return [
        Artwork(
            id=entry["id"],
            title=entry.get("title") or "Untitled",
            artist=entry.get("artist") or "Unknown artist",
            year=entry.get("year"),
            sitelinks=entry.get("sitelinks", 0),
            image_url=entry["image_url"],
            aspect_ratio=entry.get("aspect_ratio"),
        )
        for entry in raw
    ]


def download_image(artwork: Artwork, timeout: int = 30):
    """Return a PIL Image for the artwork, following the Special:FilePath redirect."""
    from io import BytesIO

    from PIL import Image

    last_exc: Optional[Exception] = None
    for attempt in range(3):
        try:
            resp = requests.get(
                artwork.image_url,
                timeout=timeout,
                headers={"User-Agent": "FrameOfTheDay/1.0 (personal wallpaper script)"},
            )
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGB")
        except Exception as exc:  # noqa: BLE001 - any failure should retry
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    raise ArtListError(f"Failed to download image for artwork {artwork.id}") from last_exc
