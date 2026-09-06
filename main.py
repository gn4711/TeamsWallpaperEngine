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


@app.command()
def main(
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML"),
    auto: bool = typer.Option(False, "--auto", help="Write directly into the Teams uploads folder"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Only show which artwork would be chosen, write nothing"
    ),
):
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
            full_path, thumb_path = teams_output.write_background(result, teams_folder)
            typer.echo(f"Written to Teams: {full_path.name} (+ thumbnail)")

    history.record_usage(history_path, artwork.id, artwork.title, artwork.artist)


if __name__ == "__main__":
    app()
