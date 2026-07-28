"""
JavaScript AST Obfuscation & Cloaking Analysis Service.
"""

import logging
from typing import Dict, Any
from collectors import JavascriptASTParser

logger = logging.getLogger(__name__)


class JavaScriptService:
    """Microservice interface for evaluating JavaScript code obfuscation and AST safety indicators."""

    @staticmethod
    def parse(js_code: str, html_content: str = "") -> Dict[str, Any]:
        """Parses JavaScript script contents and associated DOM HTML to detect obfuscation indicators."""
        try:
            return JavascriptASTParser.parse_script(js_code, html_content)
        except Exception as err:
            logger.error("Failed to parse JavaScript AST: %s", str(err), exc_info=True)
            return {
                "ast_score": 0.0,
                "eval_calls": 0,
                "obfuscated": False,
                "entropy": 0.0,
                "error": str(err)
            }

