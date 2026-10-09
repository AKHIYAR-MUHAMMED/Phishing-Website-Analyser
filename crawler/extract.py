"""
Extracts a title and visible text from HTML. Uses BeautifulSoup's html.parser backend, which
does not execute scripts or expand external entities, so parsing untrusted HTML is safe.
"""

from typing import Tuple

from bs4 import BeautifulSoup


def extract_title_and_text(html: str, max_text_chars: int = 5000) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return title, text[:max_text_chars]
