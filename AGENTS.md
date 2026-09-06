# AGENTS.md

Context for AI coding agents working on this repo. See README.md for user-facing
docs (setup, usage, config). This file is about things that aren't obvious from
reading the code once, or that have already been gotten wrong once this project's
history.

## What this is

"Frame of the Day": picks a random classic painting from a curated static list,
fits it into a picture-frame photo's aperture, and optionally pushes it into
Microsoft Teams' custom-background folder. Runs daily via a scheduled task.

## Entry points vs. internal modules

Only `main.py` (daily) and `build_art_list.py` (rare, regenerates the art list)
are ever run directly. `art_list.py`, `matcher.py`, `compositor.py`,
`teams_output.py`, `history.py`, `placeholder_frame.py` are all imported by
`main.py` - don't suggest running them standalone, they have no CLI of their own.

## Hard-won constraints - don't undo these without a reason

- **`config.yaml` is deliberately minimal.** It went through several rounds of
  bloat (safe-mode content filters, a `compositing` toggle section, Wikidata
  generation settings) that got stripped back out on request. `build_art_list.py`'s
  tunables (`MIN_AGE_YEARS`, `TARGET_COUNT`, `MIN_SITELINKS`) are constants at the
  top of that file, not config - it's a one-off tool, not part of the daily run.
  Resist moving them back into `config.yaml`.

- **Teams background selection cannot be automated.** There is no API for
  "set the active background." `teams_output.write_background()` can only drop a
  `fotd_<uuid>.jpg` / `fotd_<uuid>_thumb.jpg` pair into Teams' Uploads folder so it
  *appears* in the picker; a human still has to click it, every day. Don't imply
  otherwise in docs or code comments.

- **Never hardcode the new-Teams package folder name.** It's
  `Packages/MSTeams_<publisher-hash>` under `%LOCALAPPDATA%`. The hash suffix
  looks like `8wekyb3d8bbwe` (real Microsoft Store publisher-cert hash - not a
  bug, not a placeholder - Edge/.NET/etc. all share it), but hardcoding the exact
  folder name once already broke detection when questioned. Current code globs
  `Packages/MSTeams_*` in `find_teams_uploads_folder()` - keep it that way.

- **`art_list.json` is generated, not hand-authored.** 1000 real entries pulled
  from Wikidata (title, artist, year, image URL, aspect ratio from physical
  cm dimensions where available), ranked by `sitelinks` as a fame proxy. Editing
  individual entries by hand is fine for a quick fix, but re-running
  `build_art_list.py` overwrites the whole file - don't assume manual edits
  persist across a regeneration.

## Wikidata/SPARQL gotchas (build_art_list.py)

- `ORDER BY DESC(?sitelinks)` combined with a growing `OFFSET` gets slower every
  page and eventually 504s on the public query service. Fetch unordered pages
  (fast at any offset) and sort client-side after collecting everything instead.
- A blank/anonymous creator comes back as a raw `http://www.wikidata.org/.well-known/genid/...`
  URI in `creatorLabel` instead of a real label - detect and replace with
  "Unknown artist" (already done; don't regress it).
- Titles that fail to resolve a label come back as the raw `Q12345` QID - skip
  those entries.

## Other sources considered and rejected (context for "why not just use X")

- **Art Institute of Chicago API**: deep pagination (offset+limit > ~1000)
  returns 403 "too many results"; its IIIF image CDN also returned a Cloudflare
  JS challenge when tested from a sandboxed dev environment (may or may not
  reproduce on a real network, wasn't retested). Its `medium` search parameter
  free-text-matches the medium description field, not a real classification
  filter - don't rely on it for category filtering.
- **Met Museum API**: works fine, but only contains what the Met itself owns.
  Specific famous works elsewhere (e.g. a painting at a different national
  museum) will never appear no matter how filters are tuned - this is a
  collection-coverage limit, not a bug to work around.

## Windows-specific

- `main.py` reconfigures stdout/stderr to UTF-8 on startup - without it, artist
  names with non-ASCII characters crash `typer.echo()` under Windows' default
  cp1252 console encoding. Keep this.

## Frame aperture coordinates

`config.yaml`'s `frame.aperture` is measured pixel-for-pixel against the
specific `assets/frame.png` currently in the repo. If that image is replaced,
the aperture must be re-measured, not guessed - scan pixel brightness along a
horizontal and vertical line through the frame to find the wood-to-flat-area
transitions (that's how the current values were derived).
