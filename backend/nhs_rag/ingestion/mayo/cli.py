from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from nhs_rag.ingestion.mayo.pipeline import ingest, load_sources


async def run() -> int:
    parser = argparse.ArgumentParser(description="Build the separate Mayo symptom-checker dataset.")
    parser.add_argument("--manifest", type=Path, default=Path("config/mayo_sources.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/mayo"))
    parser.add_argument(
        "--snapshot-dir", type=Path, help="Import saved browser snapshot JSON files."
    )
    parser.add_argument("--contact", default="http://localhost/nextstep-research-prototype")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    sources = load_sources(args.manifest)
    report = await ingest(
        sources,
        output_dir=args.output_dir,
        contact=args.contact,
        snapshot_dir=args.snapshot_dir,
        delay_seconds=max(args.delay, 0),
        force=args.force,
    )
    print(
        f"Mayo dataset: {report['available']}/{report['expected']} documents; "
        f"{report['fetched']} fetched, {report['unchanged']} unchanged, {report['failed']} failed; "
        f"{report['factor_groups']} factor groups, {report['factor_options']} options."
    )
    for source in report["sources"]:
        if "error" in source:
            print(f"- {source['symptom_id']}: {source['error']}")
    return 0 if report["complete"] else 1


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
