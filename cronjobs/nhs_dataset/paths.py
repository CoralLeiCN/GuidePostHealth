from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "config" / "nhs_sources.json"
DEFAULT_HUB_CONFIG_PATH = REPOSITORY_ROOT / "config" / "huggingface.local.json"
DEFAULT_CORPUS_DIR = REPOSITORY_ROOT / "data" / "nhs"
DEFAULT_RAW_DIR = REPOSITORY_ROOT / "data" / "raw" / "nhs"
DEFAULT_DATASET_DIR = REPOSITORY_ROOT / "data" / "huggingface" / "nhs_symptom_guides"
