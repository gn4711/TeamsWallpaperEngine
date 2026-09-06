# Frame of the Day

Every day, a random classic painting from a curated static list
(`art_list.json`, generated from real Wikidata entries — think Mona Lisa,
Girl with a Pearl Earring, Wanderer above the Sea of Fog) gets fitted into
the empty aperture of a picture-frame image, composited with a soft drop
shadow and vignette, and (optionally) written straight into Microsoft
Teams' custom background folder. Title/artist/date go into an `info.txt`
next to the image, not onto the wallpaper itself.

Picking from the list at runtime is instant — no live API calls, no
scanning. All the network cost is a one-time step (`build_art_list.py`)
plus downloading the one chosen image each run.

## Setup

Requires Python 3.11+. This project uses [uv](https://docs.astral.sh/uv/) for
dependency management (a `requirements.txt` is also included for `pip`).

```bash
uv sync
```

Generate the art list once (takes a few minutes — it queries Wikidata for
real, well-known, public-domain paintings):

```bash
uv run python build_art_list.py
```

This writes `art_list.json` in the project root. Re-run it any time you want
to refresh or grow the list — edit the constants at the top of
`build_art_list.py` (`MIN_AGE_YEARS`, `TARGET_COUNT`, `MIN_SITELINKS`) to
change how many entries it gathers, how old they must be, and how strict the
"is this actually a recognizable classic" bar is. This is a one-off tool, so
its settings live there rather than in `config.yaml`.

## Usage

```bash
uv run python main.py --config config.yaml            # local output only
uv run python main.py --config config.yaml --auto     # also write to Teams
uv run python main.py --config config.yaml --dry-run  # just show the pick, write nothing
```

On first run, if `assets/frame.png` doesn't exist, a plain placeholder frame
is generated automatically (matching the aperture in `config.yaml`) so the
whole pipeline is testable before you supply a real frame photo.

## Configuring your own frame

Drop a photo of an empty picture frame at `assets/frame.png` and update
`config.yaml`'s `frame.aperture` to the pixel rectangle (`x`, `y`, `width`,
`height`) where the artwork should go, measured from the frame image's
top-left corner. An image editor's crop/selection tool is the easiest way to
find these coordinates.

## Configuration (`config.yaml`)

- **`frame.aperture`** — the artwork's target rectangle in the frame image.
- **`aspect_ratio_tolerance`** — how far an artwork's aspect ratio may deviate
  from the aperture's before falling back to `contain` mode (e.g. `0.15` =
  ±15%).
- **`fit_mode`** — `cover` (fills the aperture, crops overflow) or `contain`
  (shows the whole artwork, pads with `passepartout_color`).
- **`art_list.path`** — where to read the curated artwork list from (default
  `art_list.json`, produced by `build_art_list.py`).
- **`history.cooldown_days`** — don't reuse an artwork within this many days.
- **`output.auto_teams`** — if `true`, every run writes into the Teams
  uploads folder (same effect as always passing `--auto`).

## Modules

Only two of these files are ever run directly. The rest are internal
modules — `main.py` imports and calls them for you; you never type
`python matcher.py` or similar.

| File | Run it yourself? | Purpose |
|---|---|---|
| `main.py` | **Yes — daily.** `uv run python main.py [--auto\|--dry-run]` | CLI entry point, ties everything else together |
| `build_art_list.py` | **Yes — rarely.** `uv run python build_art_list.py` | Regenerates `art_list.json` from Wikidata |
| `art_list.py` | No (imported by `main.py`) | Loads `art_list.json`; downloads the chosen artwork's image |
| `matcher.py` | No (imported by `main.py`) | Picks the best candidate by aspect ratio + history cooldown |
| `compositor.py` | No (imported by `main.py`) | Pillow compositing: fit into aperture, drop shadow, vignette |
| `teams_output.py` | No (imported by `main.py`, only with `--auto`) | Finds the Teams uploads folder, writes the GUID-named files |
| `history.py` | No (imported by `main.py`) | Tracks which artworks were used when (cooldown enforcement) |
| `placeholder_frame.py` | No (imported by `main.py`) | Generates a plain test frame if `assets/frame.png` is missing |

## How artwork selection works

1. `build_art_list.py` (run ahead of time, not on every wallpaper change)
   queries Wikidata for real paintings that have an image, a known creator,
   and an inception date at least `MIN_AGE_YEARS` old, ranked by how many
   Wikipedia language editions cover them (`sitelinks`) as a proxy for "is
   this an actual recognizable classic." Physical width/height (in cm, from
   Wikidata) are stored as the artwork's aspect ratio where available.
2. `art_list.py` just loads that JSON at runtime — no network involved until
   an artwork is actually chosen.
3. `matcher.py` filters out recently-used candidates, then picks the first
   one within the aperture's aspect-ratio tolerance (the list is
   pre-shuffled). If nothing matches well enough, it falls back to the
   closest ratio found — `main.py` then composites that one in `contain`
   mode so nothing gets awkwardly cropped.
4. `compositor.py` fits the artwork into the aperture and adds a drop shadow
   and vignette.
5. `main.py` downloads the chosen artwork's image from Wikimedia Commons,
   writes the composited image, and writes an `info.txt` (title, artist,
   date) alongside it in the output folder.
6. `teams_output.py` (only with `--auto`) finds the Teams uploads folder,
   removes previously auto-generated backgrounds, and writes the new one as
   a GUID-named `.jpg` + `_thumb.jpg` pair, the format Teams expects.
7. `history.py` records what was used so it isn't repeated too soon.

## How the Teams background actually gets updated

This is the part that trips people up: **the script cannot make Teams show
the new image on its own.** There is no Microsoft API for "set the active
background" — Teams only lets you *pick from a folder of files*. All the
script can do is keep that folder stocked with today's image; a human still
has to select it.

### What the script does (`teams_output.py`, only with `--auto`)

1. `find_teams_uploads_folder()` locates Teams' background-upload folder —
   the same folder you'd land in if you clicked "Add new" in Teams'
   background picker. Auto-detected per OS/client:
   - Windows, classic Teams: `%APPDATA%\Microsoft\Teams\Backgrounds\Uploads`
   - Windows, new Teams (2.x, Store package): `%LOCALAPPDATA%\Packages\MSTeams_*\LocalCache\Microsoft\MSTeams\Backgrounds\Uploads` — the `MSTeams_*` segment is glob-matched, not hardcoded, since that publisher-hash suffix isn't guaranteed stable across installs/repackaging
   - macOS: `~/Library/Application Support/Microsoft/Teams/Backgrounds/Uploads` (classic) or the equivalent path under `~/Library/Containers/com.microsoft.teams2/...` (new Teams)
2. `cleanup_old_auto_generated()` deletes every file it previously wrote
   there (anything named `fotd_*`) — see "How the right file is found"
   below for why this matters.
3. `write_background()` writes the new image as a `fotd_<uuid>.jpg` /
   `fotd_<uuid>_thumb.jpg` pair — a fresh random UUID every run, not a fixed
   filename. Teams requires exactly this pair-with-matching-name pattern to
   recognize a custom background at all.

### How the right file is found, run after run

There's no "linking" or persistent reference between runs — Teams just
scans the Uploads folder's contents each time you open the background
picker and shows whatever `.jpg`/`_thumb.jpg` pairs it finds there. The
script keeps that simple by making sure exactly one `fotd_*` pair ever
exists at a time: step 2 above deletes yesterday's pair *before* step 3
writes today's. Nothing needs to be "found" by ID or matched up - old one
gone, new one written, that's the whole mechanism.

One consequence: if the script's scheduled run happens while you're
mid-meeting with a `fotd_*` background already active, that file gets
deleted out from under you. Rare in practice (schedule it well before your
day starts), but worth knowing.

### What you have to do in Teams, every day

1. Open Teams, go to your background-effects picker (in a call, or via
   Settings → Backgrounds).
2. The new thumbnail should already be there — Teams reads the Uploads
   folder fresh each time this picker opens, no restart needed.
3. **Click it to select it.** This step doesn't happen automatically and
   can't be scripted; it's the one manual action the whole pipeline can't
   replace, because Teams has no interface for a script to set someone's
   active background for them.

If you'd rather not do that daily click, the realistic alternatives are:
skip `--auto` entirely and just glance at `output/frame_of_the_day_*.jpg`
for enjoyment, or accept the one-click habit as the cost of automation.

## Running it automatically every day

### Windows (Task Scheduler)

```powershell
schtasks /create /tn "FrameOfTheDay" /tr "'E:\S\PythonRepo\TeamsWallpaperEngine\.venv\Scripts\python.exe' 'E:\S\PythonRepo\TeamsWallpaperEngine\main.py' --config 'E:\S\PythonRepo\TeamsWallpaperEngine\config.yaml' --auto" /sc daily /st 08:00
```

### macOS (launchd)

Create `~/Library/LaunchAgents/com.frameoftheday.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.frameoftheday</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/frame-of-the-day/.venv/bin/python</string>
        <string>/path/to/frame-of-the-day/main.py</string>
        <string>--config</string><string>/path/to/frame-of-the-day/config.yaml</string>
        <string>--auto</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
</dict>
</plist>
```

Then: `launchctl load ~/Library/LaunchAgents/com.frameoftheday.plist`

### macOS/Linux (cron, alternative)

```bash
crontab -e
# add:
0 8 * * * /path/to/frame-of-the-day/.venv/bin/python /path/to/frame-of-the-day/main.py --config /path/to/frame-of-the-day/config.yaml --auto
```

## Project structure

```
frame-of-the-day/
├── main.py               CLI entry point
├── build_art_list.py      one-off generator: queries Wikidata -> art_list.json
├── art_list.json           generated by build_art_list.py (curated artwork list)
├── config.yaml             configuration
├── art_list.py             loads art_list.json, downloads the chosen image
├── matcher.py              aspect-ratio + history-cooldown selection
├── compositor.py           Pillow compositing (fit, shadow, vignette)
├── teams_output.py         Teams uploads-folder integration
├── history.py              cooldown tracking
├── placeholder_frame.py    generates a test frame if none exists
├── history.json            generated at runtime
├── assets/frame.png        your frame photo goes here
├── output/info.txt         title/artist/date for the current image
└── requirements.txt
```
