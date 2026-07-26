"""
JavaScript AST Obfuscation & Cloaking Analysis Service.
"""

from typing import Dict, Any
from collectors import JavascriptASTParser


class JavaScriptService:
    @staticmethod
    def parse(js_code: str, html_content: str = "") -> Dict[str, Any]:
        return JavascriptASTParser.parse_script(js_code, html_content)
