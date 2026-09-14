from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "config" / "mayo_sources.json"
DEFAULT_RAW_DIR = REPOSITORY_ROOT / "data" / "raw" / "mayo"
