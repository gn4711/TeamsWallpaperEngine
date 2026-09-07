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

uv run python main.py --list-slots                    # show your Teams backgrounds + GUIDs
uv run python main.py --use-slot <guid>               # take over an existing background
```

On first run, if `assets/frame.png` doesn't exist, a plain placeholder frame
is generated automatically (matching the aperture in `config.yaml`) so the
whole pipeline is testable before you supply a real frame photo.

## Getting into the daily loop (Teams)

Do this once, then the painting changes on its own.

**If you already use a custom Teams background** (recommended — no clicking at
all): let the script take that one over.

```bash
uv run python main.py --list-slots
```

That prints every custom background with its GUID. Open the folder it names in
Explorer/Finder, switch to a thumbnail view, and find the one you currently
have selected in Teams. Then:

```bash
uv run python main.py --use-slot 57658d6d-67ee-46a9-9723-fdcf3ab8d114
uv run python main.py --config config.yaml --auto
```

The painting should appear in Teams without you opening the picker, because
Teams is already pointed at that GUID. Your original image is copied to
`<guid>.jpeg.bak` first — adopting a slot overwrites it.

**If you don't have one yet:** just run with `--auto`. The script creates its
own slot, and tells you to pick the new thumbnail in Teams once. After that
it behaves the same way.

```bash
uv run python main.py --config config.yaml --auto
```

Either way the chosen GUID is stored in `teams_slot.json` and reused forever.
Once this works, schedule it (see "Running it automatically" below).

### If the image doesn't change

- Teams caches the background in a live session — reopen the picker, or
  restart Teams.
- Check the slot is the one you actually have selected: `--list-slots` marks
  the current slot with `<- current slot`.
- To undo an adoption: restore the `.bak` file and delete `teams_slot.json`.

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
6. `teams_output.py` (only with `--auto`) finds the Teams uploads folder and
   overwrites its fixed `<guid>.jpeg` + `_thumb.jpeg` pair with the new image,
   so a background you selected once keeps updating.
7. `history.py` records what was used so it isn't repeated too soon.

## How the Teams background actually gets updated

Teams has no API for "set the active background," so the script can't reach in
and select an image. It gets the same result a different way: **Teams remembers
your selection as a GUID and re-reads that file's contents each time**, so the
script keeps overwriting one fixed GUID in place. Point it at a background
you've already selected and nothing needs clicking at all; point it at a new
one and you select that once.

### What the script does (`teams_output.py`, only with `--auto`)

1. `find_teams_uploads_folder()` locates Teams' background-upload folder —
   the same folder you'd land in if you clicked "Add new" in Teams'
   background picker. Only new Teams (2.x) is looked up:
   - Windows: `%LOCALAPPDATA%\Packages\MSTeams_*\LocalCache\Microsoft\MSTeams\Backgrounds\Uploads` — the `MSTeams_*` segment is glob-matched, not hardcoded, since that publisher-hash suffix isn't guaranteed stable across installs/repackaging
   - macOS: `~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/Teams/Backgrounds/Uploads`

   Classic Teams (1.x) is retired and deliberately not checked. It used to be
   tried *first*, so a leftover install would shadow the real folder and every
   run would write somewhere current Teams never reads — silently doing nothing.
2. `load_or_create_slot()` reads the GUID from `teams_slot.json`, generating
   one on first run, or adopting an existing background if you ran
   `--use-slot`. This is the entry the script owns and reuses forever.
3. `write_background()` overwrites `<guid>.<ext>` and `<guid>_thumb.<ext>` with
   today's image. Two naming rules matter: the name must be a **bare GUID**
   (any prefix and Teams won't list the file at all), and the extension must
   match whatever is already there — writing `.jpeg` next to an adopted `.png`
   would leave Teams reading the untouched original.

### The one-time setup

See "Getting into the daily loop" above. In short: adopt a background you've
already selected (`--use-slot`) and there's nothing to click, or let the
script make its own slot and select that thumbnail once in Teams.

If a running Teams session has already cached the old image, reopening the
picker (or restarting Teams) refreshes it.

If you delete `teams_slot.json`, the next run creates a new slot and you'll
need to do the one-time selection again.

## Running it automatically every day

### Windows (Task Scheduler)

The working directory matters: every path the script uses (`assets/frame.png`,
`art_list.json`, `history.json`, `teams_slot.json`) is relative to it. Task
Scheduler defaults to `C:\Windows\System32`, which would both fail to find the
frame and create a second, unused Teams slot. `schtasks` can't set a working
directory, so use `Register-ScheduledTask`:

```powershell
$root = 'Path_to_TeamsWallpaperEngine'
$action = New-ScheduledTaskAction -Execute "$root\.venv\Scripts\python.exe" `
    -Argument "main.py --config config.yaml --auto" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = 'PT2M'   # let the network come up before it downloads the artwork
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName 'FrameOfTheDay' -Action $action -Trigger $trigger -Settings $settings
```

For a fixed time instead of logon, swap the trigger for
`New-ScheduledTaskTrigger -Daily -At 08:00`. Keep `-StartWhenAvailable` on a
laptop, otherwise a run missed while the machine is off is skipped entirely.

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

Per-module purposes are in the [Modules](#modules) table above; this is just
the layout, and which files are generated rather than authored.

```
TeamsWallpaperEngine/
├── main.py                 CLI entry point
├── build_art_list.py       one-off generator: Wikidata -> art_list.json
├── art_list.py             loads art_list.json, downloads the chosen image
├── matcher.py              aspect-ratio + history-cooldown selection
├── compositor.py           Pillow compositing (fit, shadow, vignette)
├── teams_output.py         Teams uploads-folder integration
├── history.py              cooldown tracking
├── placeholder_frame.py    generates a test frame if none exists
├── config.yaml             configuration
├── AGENTS.md               notes for AI coding agents
├── pyproject.toml          project metadata + uv index config
├── uv.lock                 pinned dependency versions
├── requirements.txt        pip alternative to uv.lock
├── assets/
│   ├── frame.png           your frame photo (placeholder auto-generated if absent)
│   └── frame_prompt.md     prompt used to generate a frame image
└── output/
    ├── frame_of_the_day_<date>.jpg
    └── info.txt            title/artist/date for the current image
```

Generated rather than hand-written:

| File | Holds | Committed? |
|---|---|---|
| `art_list.json` | the curated artwork list (from `build_art_list.py`) | yes — regenerating it takes minutes of Wikidata queries |
| `history.json` | which artworks were used when, for the cooldown | no |
| `teams_slot.json` | the GUID of the Teams background being overwritten | no — it's machine-specific |
| `output/` | the composited images and `info.txt` | no |

`teams_slot.json` is the one worth keeping a note of — lose it and the script
starts a new background slot, so you have to select the thumbnail in Teams
again.
