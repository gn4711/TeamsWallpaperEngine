"""Picks the best artwork candidate from the static list: aspect-ratio fit +
history filter. Purely local/instant - no network calls."""
from __future__ import annotations

from dataclasses import dataclass

from art_list import Artwork


@dataclass
class MatchResult:
    artwork: Artwork
    ratio_diff: float  # relative deviation from target aspect ratio (inf if unknown)
    within_tolerance: bool


def target_aspect_ratio(aperture: dict) -> float:
    return aperture["width"] / aperture["height"]


def find_best_match(
    candidates: list[Artwork],
    aperture: dict,
    tolerance: float,
    used_ids: set[str],
) -> MatchResult | None:
    """Return the best candidate: first one within aspect-ratio tolerance
    wins (candidates are pre-shuffled); otherwise the closest ratio overall
    (main.py then falls back to `contain` compositing for it). Artworks
    without a known aspect ratio are only picked as a last resort.
    """
    target = target_aspect_ratio(aperture)
    best: MatchResult | None = None

    for artwork in candidates:
        if artwork.id in used_ids:
            continue

        if artwork.aspect_ratio:
            diff = abs(artwork.aspect_ratio - target) / target
        else:
            diff = float("inf")
        within = diff <= tolerance
        result = MatchResult(artwork=artwork, ratio_diff=diff, within_tolerance=within)

        if within:
            return result

        if best is None or diff < best.ratio_diff:
            best = result

    return best
