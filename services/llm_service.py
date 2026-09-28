"""
LLM API client service. Every engine result carries a status; there is no heuristic fallback
and no consensus score.
"""

from typing import Any, Dict, List, Optional

from llm_ensemble import get_llm_orchestrator


class LLMService:
    @staticmethod
    async def predict(url: str, dom_snippet: str = "") -> Dict[str, Any]:
        return await get_llm_orchestrator().run_ensemble(url, dom_snippet)

    @staticmethod
    def list_engines() -> List[Dict[str, Any]]:
        return get_llm_orchestrator().list_engines()

    @staticmethod
    async def predict_engine(engine_id: str, url: str, dom_snippet: str = "") -> Optional[Dict[str, Any]]:
        return await get_llm_orchestrator().run_single_engine(engine_id, url, dom_snippet)

    @staticmethod
    async def compare_engines(engine_ids: list, url: str, dom_snippet: str = "") -> Dict[str, Any]:
        return await get_llm_orchestrator().run_comparison(engine_ids, url, dom_snippet)
