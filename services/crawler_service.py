"""
Crawler & ingestion service.

Live URL fetching is not implemented yet (planned: Phase 2). Only HTML supplied with the
request is used. The previous version returned a synthetic page and hard-coded HTTP headers
when no HTML was supplied; that behaviour is removed.
"""

from typing import Any, Dict

from multimodal_fusion import describe_crawl


class CrawlerService:
    @staticmethod
    def crawl(url: str, html_payload: str = "") -> Dict[str, Any]:
        result = describe_crawl(url, html_payload)
        result["url"] = url
        result["html_content"] = html_payload or ""
        return result
