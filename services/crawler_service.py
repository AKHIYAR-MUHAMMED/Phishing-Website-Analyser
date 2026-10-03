"""
Crawler & ingestion service.

Fetches HTML live when the request supplies none (crawler/fetcher.py: timeout, redirect and
size limits, explicit failure states). If the request supplies HTML directly, that HTML is
used unchanged and no network request is made.
"""

from typing import Any, Dict

from multimodal_fusion import describe_crawl


class CrawlerService:
    @staticmethod
    async def crawl(url: str, html_payload: str = "") -> Dict[str, Any]:
        crawl_status, effective_html = await describe_crawl(url, html_payload)
        result = dict(crawl_status)
        result["url"] = url
        result["html_content"] = effective_html
        return result
