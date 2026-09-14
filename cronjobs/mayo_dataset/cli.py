from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from cronjobs.mayo_dataset.downloader import download_sources
from cronjobs.mayo_dataset.paths import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from cronjobs.mayo_dataset.sources import load_sources


async def run() -> int:
    parser = argparse.ArgumentParser(
        description="Download Mayo sources into raw HTML archives only."
    )
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--contact", default="https://github.com/CoralLeiCN/GuidePostHealth")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--from-browser", type=Path, help="Import full-document browser captures offline."
    )
    args = parser.parse_args()
    report = await download_sources(
        load_sources(args.manifest_path),
        raw_dir=args.raw_dir,
        contact=args.contact,
        delay_seconds=args.delay,
        force=args.force,
        capture_dir=args.from_browser,
    )
    print(
        f"Mayo raw archive: {report['archived']} archived, {report['unchanged']} unchanged, "
        f"{report['failed']} failed out of {report['expected']} sources."
    )
    for result in report["sources"]:
        if "error" in result:
            print(f"- {result['slug']}: {result['error']}")
    return 0 if report["complete"] else 1


def main() -> None:
    raise SystemExit(asyncio.run(run()))
