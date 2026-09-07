"""Source boundaries shared by discovery, parsing and export."""

import posixpath
from urllib.parse import unquote, urlparse

GUIDANCE_PATH_PREFIXES = ("/symptoms/", "/conditions/", "/mental-health/", "/pregnancy/")


def validate_nhs_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.nhs.uk":
        raise ValueError(f"Only exact https://www.nhs.uk URLs are allowed: {url}")
    path = posixpath.normpath(unquote(parsed.path)) + "/"
    if not path.startswith(GUIDANCE_PATH_PREFIXES):
        raise ValueError(f"URL is outside the curated guidance paths: {url}")
    if parsed.username or parsed.password or parsed.port:
        raise ValueError(f"URL contains disallowed authority components: {url}")
    if parsed.query or parsed.fragment or "%" in path or "\\" in path:
        raise ValueError(f"URL is not a canonical guidance path: {url}")
