"""Writes a composed wallpaper into the Microsoft Teams custom-background folder.

Teams expects each custom background as a pair of files named with the same
GUID: `<guid>.jpeg` (full image) and `<guid>_thumb.jpeg` (a small thumbnail
Teams shows in its picker).

The GUID is reused on every run rather than regenerated. Teams records the
*selected* background by GUID, so overwriting one stable name in place means a
single manual selection keeps showing each new day's image.
"""
from __future__ import annotations

import json
import os
import platform
import uuid
from pathlib import Path

from PIL import Image

THUMBNAIL_SIZE = (280, 158)  # Teams' picker thumbnail aspect (16:9-ish)
SLOT_STATE_FILENAME = "teams_slot.json"


def find_teams_uploads_folder() -> Path | None:
    """Locate the uploads folder of new Teams (2.x).

    Classic Teams (1.x) is retired and deliberately not checked: a leftover
    install would otherwise shadow the real folder and every run would write
    somewhere Teams never reads.
    """
    system = platform.system()
    candidates = []

    if system == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            # The Store package folder is Packages\MSTeams_<publisher-hash>;
            # that suffix isn't guaranteed stable, so glob rather than hardcode.
            packages_dir = Path(local_appdata) / "Packages"
            if packages_dir.exists():
                for pkg in packages_dir.glob("MSTeams_*"):
                    candidates.append(
                        pkg / "LocalCache" / "Microsoft" / "MSTeams" / "Backgrounds" / "Uploads"
                    )
    elif system == "Darwin":
        candidates = [
            Path.home()
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

    for path in candidates:
        if path.exists():
            return path
    return None


def load_or_create_slot(state_path: Path) -> tuple[str, bool]:
    """Return (guid, was_created) for the background slot this tool overwrites."""
    if state_path.exists():
        try:
            guid = json.loads(state_path.read_text(encoding="utf-8"))["slot_guid"]
            uuid.UUID(guid)  # reject anything Teams wouldn't parse as a GUID
            return guid, False
        except (OSError, ValueError, KeyError, TypeError):
            pass

    guid = str(uuid.uuid4())
    state_path.write_text(json.dumps({"slot_guid": guid}, indent=2), encoding="utf-8")
    return guid, True


def list_custom_backgrounds(folder: Path) -> list[tuple[str, Path]]:
    """Return (guid, full_image_path) for every custom background in the folder.

    Teams' own built-in backgrounds are not stored here, so everything found is
    one the user uploaded or a previous run wrote.
    """
    found = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.stem.endswith("_thumb"):
            continue
        try:
            uuid.UUID(path.stem)
        except ValueError:
            continue
        found.append((path.stem, path))
    return found


def adopt_slot(state_path: Path, guid: str, folder: Path) -> Path | None:
    """Point the slot at an existing background, backing the original up first.

    Returns the backup path, or None if there was nothing to back up.
    """
    uuid.UUID(guid)  # raises ValueError on anything Teams couldn't have written

    backup = None
    for path in folder.glob(f"{guid}*"):
        target = path.with_suffix(path.suffix + ".bak")
        if not target.exists():
            target.write_bytes(path.read_bytes())
            if not path.stem.endswith("_thumb"):
                backup = target

    state_path.write_text(json.dumps({"slot_guid": guid}, indent=2), encoding="utf-8")
    return backup


def write_background(
    image: Image.Image,
    folder: Path,
    slot_guid: str,
) -> tuple[Path, Path]:
    """Overwrite the slot's full image + thumbnail pair in a Teams uploads folder.

    Returns (full_image_path, thumbnail_path).
    """
    folder.mkdir(parents=True, exist_ok=True)

    # An adopted slot may be .png; writing .jpeg beside it would leave Teams
    # pointed at the untouched original, so reuse whatever extension is there.
    existing = [
        p for p in folder.glob(f"{slot_guid}.*")
        if p.suffix.lower() in (".jpeg", ".jpg", ".png")
    ]
    suffix = existing[0].suffix if existing else ".jpeg"
    fmt = "PNG" if suffix.lower() == ".png" else "JPEG"
    save_opts = {} if fmt == "PNG" else {"quality": 92}

    full_path = folder / f"{slot_guid}{suffix}"
    thumb_path = folder / f"{slot_guid}_thumb{suffix}"

    rgb_image = image.convert("RGB")
    rgb_image.save(full_path, fmt, **save_opts)

    thumbnail = rgb_image.copy()
    thumbnail.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    thumbnail.save(thumb_path, fmt, **({} if fmt == "PNG" else {"quality": 85}))

    return full_path, thumb_path
