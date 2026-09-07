"""Frame of the Day - CLI entry point.

Picks a classic public-domain painting from the curated art_list.json, fits
it into a picture frame's aperture, and writes the result locally and/or
straight into the Teams backgrounds folder.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
import yaml
from PIL import Image

import history
import teams_output
from art_list import ArtListError, download_image, load_art_list
from compositor import compose
from matcher import find_best_match
from placeholder_frame import ensure_frame_exists

app = typer.Typer(add_completion=False)


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _manage_slots(list_slots: bool, use_slot: str | None) -> None:
    folder = teams_output.find_teams_uploads_folder()
    if folder is None:
        typer.secho("Could not auto-detect the Teams uploads folder.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    state_path = Path(teams_output.SLOT_STATE_FILENAME)

    if list_slots:
        current, _ = teams_output.load_or_create_slot(state_path)
        backgrounds = teams_output.list_custom_backgrounds(folder)
        if not backgrounds:
            typer.echo(f"No custom backgrounds found in {folder}")
            return
        typer.echo(f"Custom backgrounds in {folder}:\n")
        for guid, path in backgrounds:
            marker = "  <- current slot" if guid == current else ""
            size_kb = path.stat().st_size // 1024
            typer.echo(f"  {guid}{path.suffix}  {size_kb:>6} KB{marker}")
        typer.echo(
            "\nOpen that folder as thumbnails to see which one you have selected "
            "in Teams, then run:\n  --use-slot <guid>"
        )
        return

    if use_slot is None:
        return

    try:
        backup = teams_output.adopt_slot(state_path, use_slot, folder)
    except ValueError:
        typer.secho(f"'{use_slot}' is not a valid GUID.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(f"Slot set to {use_slot}", fg=typer.colors.GREEN)
    if backup:
        typer.echo(f"Original backed up to: {backup.name}")
    else:
        typer.secho(
            "Note: no existing file with that GUID - Teams won't show it until "
            "you select it once.",
            fg=typer.colors.YELLOW,
        )


@app.command()
def main(
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML"),
    auto: bool = typer.Option(False, "--auto", help="Write directly into the Teams uploads folder"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Only show which artwork would be chosen, write nothing"
    ),
    list_slots: bool = typer.Option(
        False, "--list-slots", help="List existing Teams custom backgrounds and exit"
    ),
    use_slot: str = typer.Option(
        None,
        "--use-slot",
        help="Take over an existing Teams background by GUID (backs the original up)",
    ),
):
    if list_slots or use_slot:
        _manage_slots(list_slots, use_slot)
        return

    cfg = load_config(config)

    frame_path = Path(cfg["frame"]["path"])
    aperture = cfg["frame"]["aperture"]
    ensure_frame_exists(frame_path, aperture)

    history_path = Path(cfg["history"]["path"])
    used_ids = history.load_used_ids(history_path, cfg["history"]["cooldown_days"])

    art_list_path = Path(cfg.get("art_list", {}).get("path", "art_list.json"))
    try:
        candidates = load_art_list(art_list_path)
    except ArtListError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    random.shuffle(candidates)

    match = find_best_match(
        candidates=candidates,
        aperture=aperture,
        tolerance=cfg["aspect_ratio_tolerance"],
        used_ids=used_ids,
    )

    if match is None:
        typer.secho(
            "No suitable artwork found (all candidates filtered/used). Try again later.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    artwork = match.artwork
    fit_mode = cfg["fit_mode"] if match.within_tolerance else "contain"

    typer.echo(
        f"Selected: \"{artwork.title}\" by {artwork.artist} "
        f"({artwork.year}, sitelinks={artwork.sitelinks}, "
        f"ratio diff {match.ratio_diff:.1%}, "
        f"fit={fit_mode}{'' if match.within_tolerance else ' [fallback: out of tolerance]'})"
    )

    if dry_run:
        typer.echo("Dry run: no files written.")
        return

    frame_img = Image.open(frame_path)
    artwork_img = download_image(artwork)

    result = compose(
        frame_img=frame_img,
        artwork_img=artwork_img,
        aperture=aperture,
        fit_mode=fit_mode,
        passepartout_color=tuple(cfg.get("passepartout_color", [245, 242, 235])),
    )

    local_dir = Path(cfg["output"]["local_dir"])
    local_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"frame_of_the_day_{datetime.now():%Y-%m-%d}.jpg"
    local_path = local_dir / out_name
    result.save(local_path, "JPEG", quality=92)
    typer.echo(f"Saved locally: {local_path}")

    info_path = local_dir / "info.txt"
    info_path.write_text(
        f"Image: {out_name}\n"
        f"Title: {artwork.title}\n"
        f"Artist: {artwork.artist}\n"
        f"Date: {artwork.year}\n"
        f"Source: Wikimedia Commons / Wikidata (public domain)\n",
        encoding="utf-8",
    )
    typer.echo(f"Wrote info: {info_path}")

    write_to_teams = auto or cfg.get("output", {}).get("auto_teams", False)
    if write_to_teams:
        teams_folder = teams_output.find_teams_uploads_folder()
        if teams_folder is None:
            typer.secho(
                "Could not auto-detect the Teams uploads folder; "
                "skipping Teams write. Use the local file manually instead.",
                fg=typer.colors.YELLOW,
            )
        else:
            slot_guid, is_new_slot = teams_output.load_or_create_slot(
                Path(teams_output.SLOT_STATE_FILENAME)
            )
            full_path, thumb_path = teams_output.write_background(
                result, teams_folder, slot_guid
            )
            typer.echo(f"Written to Teams: {full_path.name} (+ thumbnail)")
            if is_new_slot:
                typer.secho(
                    "First run with this background slot: open Teams' background "
                    "picker and select the new thumbnail once. Future runs overwrite "
                    "that same entry, so it stays selected.",
                    fg=typer.colors.CYAN,
                )

    history.record_usage(history_path, artwork.id, artwork.title, artwork.artist)


if __name__ == "__main__":
    app()
