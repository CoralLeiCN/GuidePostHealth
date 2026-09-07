from __future__ import annotations

import argparse
import json
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from cronjobs.nhs_dataset.hub_config import HubConfig, load_hub_config
from cronjobs.nhs_dataset.paths import DEFAULT_DATASET_DIR, DEFAULT_HUB_CONFIG_PATH

_DATASET_FILES = (
    "README.md",
    "NOTICE.md",
    "metadata.json",
    "data/guides.jsonl",
    "data/sections.jsonl",
)


def _require_repository_id(config: HubConfig) -> str:
    if config.repository_id is None:
        raise ValueError(
            "Set 'namespace' in config/huggingface.local.json before using Hub transfer commands"
        )
    return config.repository_id


def validate_dataset_directory(dataset_dir: Path) -> None:
    missing = [name for name in _DATASET_FILES if not (dataset_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Dataset directory is incomplete; missing: {', '.join(missing)}")
    metadata = json.loads((dataset_dir / "metadata.json").read_text(encoding="utf-8"))
    if not isinstance(metadata.get("guide_count"), int) or metadata["guide_count"] < 1:
        raise ValueError("Dataset metadata does not contain a valid guide count")
    if not isinstance(metadata.get("section_count"), int) or metadata["section_count"] < 1:
        raise ValueError("Dataset metadata does not contain a valid section count")


def upload_dataset(
    *,
    config: HubConfig,
    dataset_dir: Path,
    commit_message: str = "Refresh NHS symptom guide dataset",
    api: HfApi | None = None,
) -> str:
    """Upload only the generated dataset repository; this function has no NHS dependency."""

    repository_id = _require_repository_id(config)
    validate_dataset_directory(dataset_dir)
    client = api or HfApi()
    repository_url = client.create_repo(
        repository_id,
        repo_type="dataset",
        private=config.private,
        exist_ok=True,
    )
    client.upload_folder(
        repo_id=repository_id,
        repo_type="dataset",
        folder_path=dataset_dir,
        allow_patterns=list(_DATASET_FILES),
        commit_message=commit_message,
    )
    return str(repository_url)


def download_dataset(
    *, config: HubConfig, dataset_dir: Path, revision: str = "main", force: bool = False
) -> Path:
    """Download a Hub dataset snapshot locally without contacting NHS.uk."""

    repository_id = _require_repository_id(config)
    result = snapshot_download(
        repo_id=repository_id,
        repo_type="dataset",
        revision=revision,
        local_dir=dataset_dir,
        force_download=force,
        allow_patterns=list(_DATASET_FILES),
    )
    if not isinstance(result, str):
        raise RuntimeError("Hugging Face download did not return a local snapshot path")
    validate_dataset_directory(dataset_dir)
    return Path(result)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload or download the generated dataset without accessing NHS.uk."
    )
    parser.add_argument(
        "--hub-config",
        type=Path,
        default=DEFAULT_HUB_CONFIG_PATH,
        help="Ignored local Hugging Face namespace and repository configuration.",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="Local Hugging Face-compatible dataset repository directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    upload = subparsers.add_parser("upload", help="Create or update the configured Hub dataset.")
    upload.add_argument(
        "--commit-message", default="Refresh NHS symptom guide dataset", help="Hub commit message."
    )
    download = subparsers.add_parser("download", help="Download the configured Hub dataset.")
    download.add_argument("--revision", default="main", help="Hub branch, tag, or commit.")
    download.add_argument(
        "--force", action="store_true", help="Force files to be downloaded again."
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = load_hub_config(args.hub_config)
    if args.command == "upload":
        url = upload_dataset(
            config=config,
            dataset_dir=args.dataset_dir,
            commit_message=args.commit_message,
        )
        print(f"Uploaded dataset to {url}")
        return
    destination = download_dataset(
        config=config,
        dataset_dir=args.dataset_dir,
        revision=args.revision,
        force=args.force,
    )
    print(f"Downloaded dataset to {destination}")


if __name__ == "__main__":
    main()
