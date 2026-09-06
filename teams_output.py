"""Writes a composed wallpaper into the Microsoft Teams custom-background folder.

Teams expects each custom background as a pair of files named with the same
GUID: `<guid>.jpg` (full image) and `<guid>_thumb.jpg` (a small thumbnail
Teams shows in its picker).
"""
from __future__ import annotations

import os
import platform
import uuid
from pathlib import Path

from PIL import Image

THUMBNAIL_SIZE = (280, 158)  # Teams' picker thumbnail aspect (16:9-ish)
MARKER_PREFIX = "fotd_"  # tag our auto-generated files so cleanup only touches those


def find_teams_uploads_folder() -> Path | None:
    """Best-effort auto-detection of the Teams custom-background uploads folder."""
    system = platform.system()

    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        candidates = []
        if appdata:
            candidates.append(
                Path(appdata) / "Microsoft" / "Teams" / "Backgrounds" / "Uploads"
            )
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            # New Teams (Teams 2.x): a Microsoft Store package under
            # Packages\MSTeams_<publisher-hash>. That hash suffix is fixed
            # per machine but not guaranteed identical across Windows/Store
            # installs or future repackaging, so glob for it rather than
            # hardcoding the exact folder name.
            packages_dir = Path(local_appdata) / "Packages"
            if packages_dir.exists():
                for pkg in packages_dir.glob("MSTeams_*"):
                    candidates.append(
                        pkg / "LocalCache" / "Microsoft" / "MSTeams" / "Backgrounds" / "Uploads"
                    )
    elif system == "Darwin":
        home = Path.home()
        candidates = [
            home
            / "Library"
            / "Application Support"
            / "Microsoft"
            / "Teams"
            / "Backgrounds"
            / "Uploads",
            home
            / "Library"
            / "Containers"
            / "com.microsoft.teams2"
            / "Data"
            / "Library"
            / "Application Support"
            / "Microsoft"
            / "Teams"
            / "Backgrounds"
            / "Uploads",
        ]
    else:
        candidates = []

    for path in candidates:
        if path.exists():
            return path
    return None


def cleanup_old_auto_generated(folder: Path) -> int:
    """Delete previously auto-generated (marker-prefixed) background files."""
    removed = 0
    for path in folder.glob(f"{MARKER_PREFIX}*"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def write_background(
    image: Image.Image,
    folder: Path,
    cleanup_previous: bool = True,
) -> tuple[Path, Path]:
    """Write the full image + thumbnail pair into a Teams uploads folder.

    Returns (full_image_path, thumbnail_path).
    """
    folder.mkdir(parents=True, exist_ok=True)

    if cleanup_previous:
        cleanup_old_auto_generated(folder)

    guid = uuid.uuid4()
    full_name = f"{MARKER_PREFIX}{guid}.jpg"
    thumb_name = f"{MARKER_PREFIX}{guid}_thumb.jpg"

    full_path = folder / full_name
    thumb_path = folder / thumb_name

    rgb_image = image.convert("RGB")
    rgb_image.save(full_path, "JPEG", quality=92)

    thumbnail = rgb_image.copy()
    thumbnail.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    thumbnail.save(thumb_path, "JPEG", quality=85)

    return full_path, thumb_path
