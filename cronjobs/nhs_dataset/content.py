"""Fail explicitly when the upstream main-content contract changes."""

from bs4 import BeautifulSoup, Tag


class UpstreamSchemaError(ValueError):
    """The source HTML no longer has the expected unambiguous content region."""


def require_main_content(soup: BeautifulSoup, *, url: str) -> Tag:
    matches = soup.select("main#maincontent")
    mains = soup.select("main")
    if len(matches) != 1 or len(mains) != 1:
        raise UpstreamSchemaError(
            f"Upstream HTML schema changed for {url}: expected exactly one "
            f"main#maincontent and one main element; found {len(matches)} matching "
            f"region(s) and {len(mains)} main element(s). Review the source template; "
            "no fallback was used."
        )
    return matches[0]
