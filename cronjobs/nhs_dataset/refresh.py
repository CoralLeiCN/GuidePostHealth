from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from cronjobs.nhs_dataset.downloader import ingest_sources, load_sources
from cronjobs.nhs_dataset.paths import (
    DEFAULT_CORPUS_DIR,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_RAW_DIR,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download the reviewed NHS text corpus into the ignored local data directory."
    )
    parser.add_argument(
        "--contact",
        default="http://localhost/guidepost-health-research-prototype",
        help="Contact URL or email included in the crawler user agent.",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between pages.")
    parser.add_argument("--limit", type=int, default=None, help="Fetch only the first N pages.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refetch and reparse pages even when conditional request metadata exists.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Tracked deduplicated NHS source manifest.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Directory for compressed raw HTML and response metadata.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
        help="Directory for downloaded parsed guide JSON.",
    )
    return parser


async def _run() -> int:
    args = _parser().parse_args()
    sources = load_sources(args.manifest_path)
    if args.limit is not None:
        sources = sources[: max(args.limit, 0)]
    report = await ingest_sources(
        sources,
        output_dir=args.corpus_dir,
        raw_dir=args.raw_dir,
        contact=args.contact,
        delay_seconds=max(args.delay, 0),
        force=args.force,
    )
    print(
        f"NHS corpus refresh complete: {report.fetched} fetched and parsed, "
        f"{report.archived} raw snapshots archived, "
        f"{report.unchanged} unchanged, {report.failed} failed."
    )
    for error in report.errors or []:
        print(f"- {error}")
    return 1 if report.failed else 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
