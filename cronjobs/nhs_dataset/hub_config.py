from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_HUB_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class HubConfig:
    namespace: str | None = None
    dataset_name: str = "nhs-symptom-guides"
    private: bool = True

    @property
    def repository_id(self) -> str | None:
        if self.namespace is None:
            return None
        return f"{self.namespace}/{self.dataset_name}"


def load_hub_config(path: Path) -> HubConfig:
    if not path.exists():
        return HubConfig()
    payload = json.loads(path.read_text(encoding="utf-8"))
    namespace_value = payload.get("namespace")
    namespace = namespace_value.strip() if isinstance(namespace_value, str) else None
    namespace = namespace or None
    dataset_name_value = payload.get("dataset_name", "nhs-symptom-guides")
    private = payload.get("private", True)

    if namespace is not None and not _HUB_NAME.fullmatch(namespace):
        raise ValueError("Hugging Face namespace may contain letters, numbers, '.', '_', or '-'")
    if not isinstance(dataset_name_value, str) or not _HUB_NAME.fullmatch(dataset_name_value):
        raise ValueError("Hugging Face dataset name is invalid")
    if not isinstance(private, bool):
        raise ValueError("Hugging Face 'private' must be true or false")
    return HubConfig(namespace=namespace, dataset_name=dataset_name_value, private=private)
