"""
10-LLM Bayesian Orchestrator Dedicated Microservice.
Exposes POST /models/llm/predict endpoint running 10 concurrent LLM providers with Bayesian evidence fusion.
"""

from typing import Dict, Any
from llm_ensemble import get_llm_orchestrator


class LLMService:
    @staticmethod
    async def predict(url: str, dom_snippet: str, lexical_features: Dict[str, Any], gnn_stats: Dict[str, Any]) -> Dict[str, Any]:
        orchestrator = get_llm_orchestrator()
        return await orchestrator.run_ensemble(url, dom_snippet, lexical_features, gnn_stats)

    @staticmethod
    def list_engines():
        orchestrator = get_llm_orchestrator()
        return orchestrator.list_engines()

    @staticmethod
    async def predict_engine(engine_id: str, url: str, dom_snippet: str = "", lexical_features: Dict[str, Any] = None, gnn_stats: Dict[str, Any] = None) -> Dict[str, Any]:
        orchestrator = get_llm_orchestrator()
        return await orchestrator.run_single_engine(engine_id, url, dom_snippet, lexical_features, gnn_stats)

    @staticmethod
    async def compare_engines(engine_ids: list, url: str, dom_snippet: str = "", lexical_features: Dict[str, Any] = None, gnn_stats: Dict[str, Any] = None) -> Dict[str, Any]:
        orchestrator = get_llm_orchestrator()
        return await orchestrator.run_comparison(engine_ids, url, dom_snippet, lexical_features, gnn_stats)

