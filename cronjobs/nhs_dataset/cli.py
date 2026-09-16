from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from cronjobs.nhs_dataset.discovery import discover_source_manifest, write_source_manifest
from cronjobs.nhs_dataset.downloader import (
    ingest_sources,
    load_sources,
    reparse_sources_from_raw,
)
from cronjobs.nhs_dataset.exporter import export_huggingface_dataset
from cronjobs.nhs_dataset.hub_config import load_hub_config
from cronjobs.nhs_dataset.paths import (
    DEFAULT_CORPUS_DIR,
    DEFAULT_DATASET_DIR,
    DEFAULT_HUB_CONFIG_PATH,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_RAW_DIR,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover, deduplicate, download, and export every NHS Symptoms A-to-Z guide "
            "as a Hugging Face-compatible dataset repository."
        )
    )
    parser.add_argument(
        "--contact",
        default="https://github.com/guidepost-health/guidepost-health",
        help="Contact URL or email included in the crawler user agent.",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between guide pages.")
    parser.add_argument("--force", action="store_true", help="Refetch all guide pages.")
    parser.add_argument(
        "--skip-discovery", action="store_true", help="Use the existing source manifest."
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--skip-download", action="store_true", help="Export the existing parsed corpus."
    )
    input_group.add_argument(
        "--from-raw",
        action="store_true",
        help="Do not use the network; reparse the corpus from archived HTML before export.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Tracked deduplicated NHS source manifest.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
        help="Directory for downloaded parsed guide JSON.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Directory for compressed raw HTML and response metadata.",
    )
    parser.add_argument(
        "--hub-config",
        type=Path,
        default=DEFAULT_HUB_CONFIG_PATH,
        help="Ignored local Hugging Face namespace and repository configuration.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="Hugging Face dataset repository directory.",
    )
    return parser


async def _run() -> int:
    args = _parser().parse_args()
    hub_config = load_hub_config(args.hub_config)
    if not args.skip_discovery and not args.from_raw:
        manifest = await discover_source_manifest(contact=args.contact)
        write_source_manifest(manifest, args.manifest_path)
        print(
            f"Discovered {manifest['index_entry_count']} index entries pointing to "
            f"{manifest['unique_guide_count']} unique guides."
        )

    sources = load_sources(args.manifest_path)
    if args.from_raw:
        reparse = reparse_sources_from_raw(
            sources, raw_dir=args.raw_dir, output_dir=args.corpus_dir
        )
        print(
            f"Offline NHS corpus reparse complete: {reparse.reparsed} reparsed, "
            f"{reparse.failed} failed."
        )
        for error in reparse.errors:
            print(f"- {error}")
        if reparse.failed:
            return 1
    elif not args.skip_download:
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
        for error in report.errors:
            print(f"- {error}")
        if report.failed:
            return 1

    export = export_huggingface_dataset(
        manifest_path=args.manifest_path,
        corpus_dir=args.corpus_dir,
        output_dir=args.output_dir,
        hub_config=hub_config,
    )
    print(
        f"Hugging Face dataset ready: {export.guides} unique guides and "
        f"{export.sections} sections in {export.output_dir}."
    )
    if export.repository_id:
        visibility = "private" if hub_config.private else "public"
        print(
            f"Configured Hugging Face destination: {export.repository_id} "
            f"({visibility}); nothing was uploaded."
        )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
