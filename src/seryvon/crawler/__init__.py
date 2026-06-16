"""Crawler : découverte (M1), crawl multi-pages (M2) et extraction de signaux."""

from seryvon.crawler.crawl import PageFetcher, Sleeper, crawl_site, detect_render_mode
from seryvon.crawler.discovery import (
    DiscoveryResult,
    NormalizedUrl,
    RobotsTxt,
    SitemapParseResult,
    discover,
    normalize_url,
    parse_sitemap,
    same_host,
)
from seryvon.crawler.extract import extract_links, extract_page_signals
from seryvon.crawler.fetch import FetchedResource, FetchResult, fetch_page, fetch_resource

__all__ = [
    "DiscoveryResult",
    "FetchResult",
    "FetchedResource",
    "NormalizedUrl",
    "PageFetcher",
    "RobotsTxt",
    "SitemapParseResult",
    "Sleeper",
    "crawl_site",
    "detect_render_mode",
    "discover",
    "extract_links",
    "extract_page_signals",
    "fetch_page",
    "fetch_resource",
    "normalize_url",
    "parse_sitemap",
    "same_host",
]
