from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

_PATH = re.compile(r"/symptom-checker/[a-z0-9-]+-(adult|child)/related-factors/itt-20009075")
ROBOTS_URL = "https://www.mayoclinic.org/robots.txt"


class MayoSource(BaseModel):
    title: str
    url: str
    population: Literal["adult", "child"]

    @property
    def slug(self) -> str:
        return self.url.split("/")[4]


def validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.mayoclinic.org"
        or parsed.query
        or parsed.fragment
        or not _PATH.fullmatch(parsed.path)
    ):
        raise ValueError(f"Not an allowed Mayo symptom-checker URL: {url}")


def load_sources(path: Path) -> list[MayoSource]:
    sources = [MayoSource.model_validate(s) for s in json.loads(path.read_text())["sources"]]
    for source in sources:
        validate_url(source.url)
        if not source.slug.endswith(f"-{source.population}"):
            raise ValueError("Source population does not match URL")
    if not sources or len({s.slug for s in sources}) != len(sources):
        raise ValueError("Manifest must contain distinct source filenames")
    return sources
