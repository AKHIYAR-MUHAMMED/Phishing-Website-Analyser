"""
JavaScript indicator service.

Regex pattern counts over script text and HTML. This is a heuristic, not an AST parser,
and it produces no risk score.
"""

from typing import Any, Dict

from multimodal_fusion import analyse_javascript


class JavaScriptService:
    @staticmethod
    def parse(js_code: str, html_content: str = "") -> Dict[str, Any]:
        return analyse_javascript(" ".join(part for part in (js_code, html_content) if part))
