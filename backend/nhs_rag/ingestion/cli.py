from __future__ import annotations

import argparse
import asyncio

from nhs_rag.ingestion.pipeline import ingest_sources, load_sources
from nhs_rag.settings import get_settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download the reviewed NHS text corpus into the ignored local data directory."
    )
    parser.add_argument(
        "--contact",
        default="http://localhost/nextstep-research-prototype",
        help="Contact URL or email included in the crawler user agent.",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between pages.")
    parser.add_argument("--limit", type=int, default=None, help="Fetch only the first N pages.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refetch and reparse pages even when conditional request metadata exists.",
    )
    return parser


async def _run() -> int:
    args = _parser().parse_args()
    settings = get_settings()
    sources = load_sources(settings.source_manifest)
    if args.limit is not None:
        sources = sources[: max(args.limit, 0)]
    report = await ingest_sources(
        sources,
        output_dir=settings.corpus_dir,
        contact=args.contact,
        delay_seconds=max(args.delay, 0),
        force=args.force,
    )
    print(
        f"NHS corpus refresh complete: {report.fetched} fetched, "
        f"{report.unchanged} unchanged, {report.failed} failed."
    )
    for error in report.errors or []:
        print(f"- {error}")
    return 1 if report.failed else 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
