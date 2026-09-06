"""One-off/occasional generator for art_list.json.

Queries Wikidata for real, well-known public-domain paintings (has an image,
has a creator, at least `min_age_years` old going by inception date) and
writes them to art_list.json. This runs once (or whenever you want to
refresh/grow the list) - the main pipeline just reads the resulting JSON at
runtime, no live querying needed there.

Ranked by Wikidata sitelinks (how many Wikipedia language editions have an
article on it) as a proxy for "is this an actual recognizable classic" vs an
obscure minor work.

Tune the constants below and re-run to grow/refresh art_list.json. This is a
one-off/occasional tool, not part of the daily wallpaper run, so its knobs
live here rather than in config.yaml.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

SPARQL_URL = "https://query.wikidata.org/sparql"
OUTPUT_PATH = Path(__file__).parent / "art_list.json"

MIN_AGE_YEARS = 200
TARGET_COUNT = 1000
MIN_SITELINKS = 3  # lower bound; drop obscure/unverified items

QUERY_TEMPLATE = """
SELECT ?item ?itemLabel ?image ?creatorLabel ?inception ?sitelinks ?heightCm ?widthCm WHERE {{
  ?item wdt:P31 wd:Q3305213;
        wdt:P18 ?image;
        wdt:P571 ?inception;
        wdt:P170 ?creator;
        wikibase:sitelinks ?sitelinks.
  FILTER(YEAR(?inception) <= {cutoff_year})
  FILTER(?sitelinks >= {min_sitelinks})
  OPTIONAL {{ ?item p:P2048/psv:P2048/wikibase:quantityAmount ?heightCm. }}
  OPTIONAL {{ ?item p:P2049/psv:P2049/wikibase:quantityAmount ?widthCm. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {limit}
OFFSET {offset}
"""
# Deliberately no ORDER BY here: sorting the whole (large) matching set by
# sitelinks before paging gets slower and slower as OFFSET grows, until the
# shared Wikidata query service times out (504). Unordered paging stays fast
# at any offset; we sort by sitelinks ourselves after collecting everything.


def _filename_from_special_filepath(image_url: str) -> str:
    """Extract the plain Commons filename from a Special:FilePath URL."""
    path = urlparse(image_url).path
    return unquote(path.rsplit("/", 1)[-1])


def fetch_batch(cutoff_year: int, min_sitelinks: int, limit: int, offset: int) -> list[dict]:
    query = QUERY_TEMPLATE.format(
        cutoff_year=cutoff_year, min_sitelinks=min_sitelinks, limit=limit, offset=offset
    )
    resp = requests.get(
        SPARQL_URL,
        params={"query": query, "format": "json"},
        headers={"User-Agent": "FrameOfTheDay/1.0 (personal wallpaper script)"},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["results"]["bindings"]


def main() -> None:
    cutoff_year = datetime.now().year - MIN_AGE_YEARS
    target_count = TARGET_COUNT
    min_sitelinks = MIN_SITELINKS
    output_path = OUTPUT_PATH

    print(
        f"Generating up to {target_count} entries: inception year <= {cutoff_year}, "
        f"sitelinks >= {min_sitelinks}",
        flush=True,
    )

    seen_ids = set()
    entries = []

    offset = 0
    page_size = 300
    consecutive_failures = 0
    max_offset = 20_000  # safety cap so a stuck query service can't loop forever

    while len(entries) < target_count and offset < max_offset:
        print(f"Querying Wikidata (offset={offset})...", flush=True)
        try:
            rows = fetch_batch(cutoff_year, min_sitelinks, page_size, offset)
        except requests.RequestException as exc:
            print(f"  query failed ({exc.__class__.__name__}), retrying next page...", file=sys.stderr)
            consecutive_failures += 1
            offset += page_size
            if consecutive_failures >= 5:
                print("Too many consecutive failures, stopping.", file=sys.stderr)
                break
            time.sleep(3)
            continue

        consecutive_failures = 0
        if not rows:
            print("  no more results - reached the end of the matching set.", flush=True)
            break

        for row in rows:
            item_id = row["item"]["value"]
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            title = row.get("itemLabel", {}).get("value") or "Untitled"
            if title.startswith("Q") and title[1:].isdigit():
                continue  # no real label resolved, skip

            artist = row.get("creatorLabel", {}).get("value") or "Unknown artist"
            if artist.startswith("http"):
                # anonymous/disputed creator: Wikidata has a blank-node
                # placeholder instead of a real, labelable entity
                artist = "Unknown artist"

            image_url = row["image"]["value"]
            filename = _filename_from_special_filepath(image_url)

            height_cm = row.get("heightCm", {}).get("value")
            width_cm = row.get("widthCm", {}).get("value")
            aspect_ratio = None
            if height_cm and width_cm:
                try:
                    aspect_ratio = round(float(width_cm) / float(height_cm), 4)
                except (ValueError, ZeroDivisionError):
                    aspect_ratio = None

            entries.append(
                {
                    "id": item_id.rsplit("/", 1)[-1],
                    "title": title,
                    "artist": artist,
                    "year": int(row["inception"]["value"][:4]),
                    "sitelinks": int(row["sitelinks"]["value"]),
                    "image_url": f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}",
                    "aspect_ratio": aspect_ratio,
                }
            )

        print(f"  -> {len(entries)} entries so far", flush=True)
        offset += page_size
        time.sleep(1)  # be polite to the shared query service

    entries.sort(key=lambda e: -e["sitelinks"])
    entries = entries[:target_count]
    output_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {output_path}")


if __name__ == "__main__":
    main()
