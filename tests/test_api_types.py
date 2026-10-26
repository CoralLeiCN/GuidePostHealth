import runpy
from pathlib import Path


def test_frontend_wire_types_match_backend_models() -> None:
    root = Path(__file__).resolve().parents[1]
    generator = runpy.run_path(str(root / "scripts" / "generate_api_types.py"))
    assert (root / "lib" / "api-types.ts").read_text(encoding="utf-8") == generator["render"]()
