"""Utilities for auto-filling Notion paper archive entries.

This script queries a Notion database for pages whose title has been filled 
by the user but which are still missing extra metadata.  

Usage example::

    python notion_paper_archive.py \
        --notion-token <your integration token> \
        --database-id <your db id> \
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import os
import textwrap
from typing import Dict, Iterable, List, Optional

import requests

NOTION_VERSION = "2022-06-28"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
NOTION_DATABASE_ID = " " ## input your database id here
NOTION_TOKEN= " " ## input your notion token here



@dataclasses.dataclass
class PropertyConfig:
    """Mapping between logical fields and Notion property names."""

    title: str = "Name"
    authors: Optional[str] = "Author" ## input your authors property name here
    published: Optional[str] = "Year" ## like above
    venue: Optional[str] = "Venue"
    citation: Optional[str] = "Citation"
    abstract: Optional[str] = "Abstract"


class NotionPaperArchive:
    def __init__(self, token: str, database_id: str, props: PropertyConfig):
        self.token = token
        self.database_id = database_id
        self.props = props
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Notion-Version": NOTION_VERSION,
            }
        )

    # ------------------------------------------------------------------
    def run(self, dry_run: bool = False) -> None:
        pages = list(self._iter_pages())
        logging.info("Found %s pages in database", len(pages))
        updated = 0

        for page in pages:
            title = self._extract_title(page)
            if not title:
                continue

            missing_fields = self._missing_fields(page)
            if not missing_fields:
                logging.debug("Skipping '%s' (already filled)", title)
                continue

            metadata = fetch_metadata(title)
            if not metadata:
                logging.warning("Could not find metadata for '%s'", title)
                continue

            payload = self._build_update_payload(page, metadata)
            if not payload:
                continue

            logging.info("Updating '%s' with %s fields", title, list(payload))
            if dry_run:
                continue

            self._patch_page(page["id"], payload)
            updated += 1

        logging.info("Updated %s pages", updated)

    # ------------------------------------------------------------------
    def _patch_page(self, page_id: str, properties: Dict[str, Dict]) -> None:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        response = self.session.patch(url, json={"properties": properties}, timeout=30)
        response.raise_for_status()

    # ------------------------------------------------------------------
    def _iter_pages(self) -> Iterable[Dict]:
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload: Dict[str, object] = {"page_size": 100}

        while True:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            yield from data.get("results", [])

            if not data.get("has_more"):
                break
            payload["start_cursor"] = data["next_cursor"]

    # ------------------------------------------------------------------
    def _missing_fields(self, page: Dict) -> List[str]:
        missing = []
        properties = page.get("properties", {})
        for attr in ("authors", "published", "venue", "citation", "abstract"):
            prop_name = getattr(self.props, attr)
            if not prop_name:
                continue
            prop = properties.get(prop_name)
            if not prop:
                continue
            if not property_has_value(prop):
                missing.append(prop_name)
        return missing

    # ------------------------------------------------------------------
    def _extract_title(self, page: Dict) -> str:
        properties = page.get("properties", {})
        title_prop = properties.get(self.props.title)
        if not title_prop:
            return ""
        if title_prop["type"] != "title":
            return ""
        return "".join(part.get("plain_text", "") for part in title_prop["title"]).strip()

    # ------------------------------------------------------------------
    def _build_update_payload(self, page: Dict, metadata: Dict) -> Dict[str, Dict]:
        payload: Dict[str, Dict] = {}
        properties = page.get("properties", {})

        def maybe_set(prop_name: Optional[str], value_builder):
            if not prop_name:
                return
            prop = properties.get(prop_name)
            if not prop or property_has_value(prop):
                return
            value = value_builder()
            if value is None:
                return
            payload[prop_name] = value

        maybe_set(self.props.authors, lambda: build_property_value(properties.get(self.props.authors), metadata.get("authors")))
        maybe_set(
            self.props.published,
            lambda: build_property_value(properties.get(self.props.published), metadata.get("publication_date")),
        )
        maybe_set(self.props.venue, lambda: build_property_value(properties.get(self.props.venue), metadata.get("venue")))
        maybe_set(self.props.citation, lambda: build_property_value(properties.get(self.props.citation), metadata.get("citation")))
        maybe_set(
            self.props.abstract,
            lambda: build_property_value(properties.get(self.props.abstract), metadata.get("abstract")),
        )
        return payload


# ---------------------------------------------------------------------------
def property_has_value(prop: Dict) -> bool:
    """Return True if the given Notion property already contains data."""

    prop_type = prop.get("type")
    value = prop.get(prop_type)
    if value is None:
        return False
    if prop_type in {"title", "rich_text", "multi_select"}:
        return bool(value)
    if prop_type == "date":
        return bool(value.get("start"))
    return False


def build_property_value(prop: Optional[Dict], value):
    if value in (None, ""):
        return None
    if not prop:
        return None

    prop_type = prop.get("type")
    if prop_type == "rich_text":
        return {"rich_text": build_rich_text(value)}
    if prop_type == "title":
        return {"title": build_rich_text(value)}
    if prop_type == "multi_select":
        if isinstance(value, str):
            values = [part.strip() for part in value.split(",") if part.strip()]
        else:
            values = list(value)
        return {"multi_select": [{"name": v} for v in values[:100]]}
    if prop_type == "date":
        if isinstance(value, str):
            return {"date": {"start": value}}
    return None


def build_rich_text(value: str) -> List[Dict]:
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    if value is None:
        return []
    text = value.strip()
    if not text:
        return []
    chunks = textwrap.wrap(text, width=1800) or [text]
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]


# ---------------------------------------------------------------------------
def fetch_metadata(title: str) -> Optional[Dict]:
    params = {
        "query": title,
        "limit": 1,
        "fields": "title,authors,year,venue,publicationDate,abstract,citationCount",
    }
    response = requests.get(SEMANTIC_SCHOLAR_URL, params=params, timeout=30)
    if not response.ok:
        logging.warning("Semantic Scholar lookup failed (%s) for '%s'", response.status_code, title)
        return None
    data = response.json()
    papers = data.get("data") or []
    if not papers:
        return None

    paper = papers[0]
    authors = [author.get("name", "").strip() for author in paper.get("authors", []) if author.get("name")]
    venue = paper.get("venue") or paper.get("publicationVenue", {}).get("name")
    year = paper.get("year")
    publication_date = paper.get("publicationDate") or (f"{year}-01-01" if year else None)
    citation = format_citation(title=paper.get("title"), authors=authors, year=year, venue=venue)

    return {
        "title": paper.get("title", title),
        "authors": authors,
        "venue": venue,
        "year": year,
        "publication_date": publication_date,
        "citation": citation,
        "abstract": paper.get("abstract"),
    }


def format_citation(title: Optional[str], authors: List[str], year: Optional[int], venue: Optional[str]) -> Optional[str]:
    if not title:
        return None
    main_authors = authors[:3]
    if not main_authors:
        author_text = "Unknown"
    elif len(authors) <= 3:
        author_text = ", ".join(main_authors)
    else:
        author_text = f"{', '.join(main_authors)} et al."

    venue_part = f" {venue}." if venue else ""
    year_part = f" ({year})" if year else ""
    return f"{author_text}{year_part}. {title}.{venue_part}".strip()


# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-fill Notion paper archives")
    parser.add_argument("--database-id", default=NOTION_DATABASE_ID, help="Target Notion database ID")
    parser.add_argument("--notion-token", default=NOTION_TOKEN, help="Notion integration token")
    parser.add_argument("--dry-run", action="store_true", help="Only print actions without updating Notion")
    parser.add_argument("--log-level", default="INFO", help="Python logging level (default: INFO)")
    args = parser.parse_args()

    if not args.database_id:
        parser.error("--database-id or NOTION_DATABASE_ID is required")
    if not args.notion_token:
        parser.error("--notion-token or NOTION_TOKEN is required")
    return args


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    props = PropertyConfig()

    archive = NotionPaperArchive(args.notion_token, args.database_id, props)
    archive.run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
