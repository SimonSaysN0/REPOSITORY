from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

IS_PATTERN = re.compile(r"\b(?:IS|ISO|IEC|IS/ISO|IS/IEC)\s*[/A-Z]*\s*\d+(?:\s*\([^)]*\))?(?:\s*:\s*\d{4})?\b", re.I)
FIELD_LABELS = {
    "is_number": ("standard number", "is number", "standard no"),
    "title": ("title", "standard title"),
    "edition_year": ("edition year", "year"),
    "publication_date": ("date of publish", "publication date", "date published"),
    "department": ("department",),
    "technical_committee": ("technical committee", "committee"),
    "type_of_standard": ("type of standard", "type"),
    "sector": ("classification", "sector"),
    "status": ("status", "standard status"),
    "number_of_revisions": ("number of revisions", "revisions"),
    "number_of_amendments": ("number of amendments", "amendments"),
    "amendment_year": ("amendment year",),
    "reaffirmation_year": ("reaffirmation year",),
    "certification": ("certification",),
    "superseding_standard": ("superseding standard", "superseded by"),
}
REFERENCE_HEADINGS = ("indian standards referred in", "referred standards", "referred indian standards")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_label_value(soup: BeautifulSoup, aliases: tuple[str, ...]) -> str:
    """Read label/value pairs from common table and definition-list layouts."""
    wanted = {a.casefold().rstrip(":") for a in aliases}
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) >= 2 and _clean(cells[0].get_text(" ", strip=True)).casefold().rstrip(":") in wanted:
            return _clean(" ".join(c.get_text(" ", strip=True) for c in cells[1:]))
    for term in soup.select("dt"):
        if _clean(term.get_text(" ", strip=True)).casefold().rstrip(":") in wanted:
            desc = term.find_next_sibling("dd")
            if desc: return _clean(desc.get_text(" ", strip=True))
    # Label/value div pairs; require an exact field-label match, not fuzzy body-text search.
    for label in soup.find_all(["label", "strong", "b", "span"]):
        if _clean(label.get_text(" ", strip=True)).casefold().rstrip(":") not in wanted:
            continue
        sibling = label.find_next_sibling()
        if sibling: return _clean(sibling.get_text(" ", strip=True))
        parent = label.parent
        if parent:
            text = _clean(parent.get_text(" ", strip=True))
            for alias in aliases:
                if text.casefold().startswith(alias.casefold()):
                    return _clean(text[len(alias):].lstrip(" :\t"))
    return ""


def extract_references(soup: BeautifulSoup) -> list[str]:
    """Extract IS-like identifiers from a visibly named referred-standards section."""
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "th", "strong", "b"]):
        label = _clean(heading.get_text(" ", strip=True)).casefold().rstrip(":")
        if label not in REFERENCE_HEADINGS:
            continue
        section = heading.parent
        # Capture nearby section/table/list content, without scanning the entire page.
        chunks = [section.get_text(" ", strip=True)] if section else []
        node = section.find_next_sibling() if section else None
        for _ in range(8):
            if node is None or getattr(node, "name", "") in {"h1", "h2", "h3", "h4"}: break
            chunks.append(node.get_text(" ", strip=True))
            node = node.find_next_sibling()
        combined = " ".join(chunks)
        return list(dict.fromkeys(_clean(x) for x in IS_PATTERN.findall(combined)))
    return []


def parse_detail(html: str, source_url: str) -> tuple[dict[str, str], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    data = {name: extract_label_value(soup, aliases) for name, aliases in FIELD_LABELS.items()}
    data["source_url"] = source_url
    if not data["title"]:
        # The page title is a fallback only; keep missing source fields explicitly blank.
        heading = soup.find(["h1", "h2"])
        if heading: data["title"] = _clean(heading.get_text(" ", strip=True))
    if not data["is_number"]:
        page_text = soup.get_text(" ", strip=True)
        match = IS_PATTERN.search(page_text)
        if match: data["is_number"] = _clean(match.group(0))
    return data, extract_references(soup)


def extract_detail_entries(html: str, listing_url: str, selector: str) -> list[tuple[str, str]]:
    if not selector:
        raise ValueError("Set BIS_DETAIL_LINK_SELECTOR after inspecting the catalogue's real detail links.")
    soup = BeautifulSoup(html, "html.parser")
    origin = urlparse(listing_url)
    found: list[tuple[str, str]] = []
    for anchor in soup.select(selector):
        href = anchor.get("href")
        if not href: continue
        absolute = urljoin(listing_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.casefold() != origin.netloc.casefold():
            continue
        context = anchor.find_parent("tr") or anchor.parent
        context_text = _clean(context.get_text(" ", strip=True)) if context else _clean(anchor.get_text(" ", strip=True))
        is_match = IS_PATTERN.search(context_text) or IS_PATTERN.search(_clean(anchor.get_text(" ", strip=True)))
        standard_id = _clean(is_match.group(0)) if is_match else ""
        entry = (standard_id, absolute)
        if entry not in found: found.append(entry)
    return found
