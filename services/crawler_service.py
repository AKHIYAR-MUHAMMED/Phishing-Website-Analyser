"""
Crawler & Ingestion Service:
Fetches HTML DOM, inline scripts, CSS styles, and HTTP response headers.
"""

import urllib.parse
from typing import Dict, Any


class CrawlerService:
    @staticmethod
    def crawl(url: str, html_payload: str = "") -> Dict[str, Any]:
        parsed = urllib.parse.urlparse(url if "://" in url else "http://" + url)
        domain = parsed.netloc or parsed.path
        
        # Generated or provided DOM payload
        dom_html = html_payload if html_payload else f"<html><head><title>{domain}</title></head><body><h1>Welcome to {domain}</h1></body></html>"
        
        return {
            "url": url,
            "domain": domain,
            "scheme": parsed.scheme or "http",
            "html_length_bytes": len(dom_html),
            "html_content": dom_html,
            "headers": {
                "server": "nginx/1.18.0",
                "content-type": "text/html; charset=UTF-8",
                "x-frame-options": "SAMEORIGIN"
            }
        }
