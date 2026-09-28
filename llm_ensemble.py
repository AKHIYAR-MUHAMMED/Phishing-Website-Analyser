"""
LLM API clients for phishing analysis (legacy multi-provider module).

Phase 0 honesty pass:
- Only five engines have an API client (OpenAI, Anthropic, Google Gemini, DeepSeek, Mistral).
  The other five listed engines have no client in this repository and report "not_implemented".
- A missing API key reports "unavailable"; a failed or unparseable call reports "error".
  There is NO heuristic fallback and NO default verdict or score.
- A result is "ok" only when the provider returned a JSON object with a valid verdict and a
  threat_score in [0, 100]. The reasoning text is model-generated.
- No consensus score is computed. The earlier "Bayesian consensus" used literal reliabilities
  and is removed. A single semantic language-model branch is planned (Phase 6).
- Model IDs are read from environment variables. The defaults below were inherited from the
  previous code and have NOT been verified against the provider APIs.
"""

import os
import re
import json
import time
import asyncio
from typing import Any, Callable, Dict, List, Optional

import httpx

from component_status import REASONS, UNAVAILABLE, NOT_IMPLEMENTED

REQUEST_TIMEOUT_SECONDS = 8.0

STATUS_OK = "ok"
STATUS_ERROR = "error"

SYSTEM_PROMPT = (
    "You are a cybersecurity analyst. Decide whether the webpage is a phishing page. "
    "Respond ONLY with a JSON object: "
    '{"threat_score": number between 0 and 100, "verdict": "PHISHING" or "LEGITIMATE", '
    '"reasoning": string}'
)


def _user_prompt(url: str, dom_snippet: str) -> str:
    snippet = dom_snippet if dom_snippet else "(no HTML supplied)"
    return f"URL: {url}\nHTML snippet (first 1000 characters):\n{snippet}"


def parse_llm_json(text: str) -> Dict[str, Any]:
    """Extract and validate the JSON answer. Raises ValueError if anything is missing or invalid."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise ValueError("response contains no JSON object")
    parsed = json.loads(match.group(0))

    verdict = str(parsed.get("verdict", "")).strip().upper()
    if verdict not in ("PHISHING", "LEGITIMATE"):
        raise ValueError(f"invalid or missing verdict: {parsed.get('verdict')!r}")

    if "threat_score" not in parsed:
        raise ValueError("missing threat_score")
    score = float(parsed["threat_score"])
    if not 0.0 <= score <= 100.0:
        raise ValueError(f"threat_score out of range: {score}")

    return {"verdict": verdict, "threat_score": score, "reasoning": str(parsed.get("reasoning", ""))}


# --- Provider request builders: return (endpoint, headers, body, text_extractor) ---

def _openai_compatible(base_url: str) -> Callable:
    def build(api_key: str, model: str, url: str, dom_snippet: str):
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(url, dom_snippet)},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        return f"{base_url}/chat/completions", headers, body, lambda d: d["choices"][0]["message"]["content"]
    return build


def _anthropic(api_key: str, model: str, url: str, dom_snippet: str):
    body = {
        "model": model,
        "max_tokens": 500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _user_prompt(url, dom_snippet)}],
    }
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    return "https://api.anthropic.com/v1/messages", headers, body, lambda d: d["content"][0]["text"]


def _gemini(api_key: str, model: str, url: str, dom_snippet: str):
    body = {
        "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + _user_prompt(url, dom_snippet)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    return endpoint, headers, body, lambda d: d["candidates"][0]["content"]["parts"][0]["text"]


class LLMEngine:
    """One LLM engine. `provider` is None when no API client exists in this repository."""

    def __init__(self, name: str, developer: str, key_env: str,
                 provider: Optional[Callable] = None, model_env: str = "", default_model: str = ""):
        self.name = name
        self.developer = developer
        self.key_env = key_env
        self.provider = provider
        self.model_env = model_env
        self.default_model = default_model

    @property
    def engine_id(self) -> str:
        return re.sub(r"[^a-z0-9]", "", self.name.lower())

    @property
    def implemented(self) -> bool:
        return self.provider is not None

    @property
    def api_key(self) -> str:
        return os.getenv(self.key_env, "") if self.key_env else ""

    @property
    def model(self) -> str:
        return os.getenv(self.model_env, self.default_model) if self.model_env else ""

    def _result(self, status: str, **fields) -> Dict[str, Any]:
        return {"engine": self.name, "engine_id": self.engine_id, "developer": self.developer,
                "model": self.model or None, "status": status, **fields}

    async def analyze(self, url: str, dom_snippet: str = "") -> Dict[str, Any]:
        if not self.implemented:
            return self._result(NOT_IMPLEMENTED, reason="No API client exists for this engine in the repository.")
        if not self.api_key:
            return self._result(UNAVAILABLE, reason=f"API key not configured (environment variable {self.key_env}).")

        start = time.perf_counter()
        try:
            endpoint, headers, body, extract_text = self.provider(self.api_key, self.model, url, dom_snippet)
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(endpoint, headers=headers, json=body)
            latency_ms = round((time.perf_counter() - start) * 1000.0, 1)
            if resp.status_code != 200:
                return self._result(STATUS_ERROR, reason=f"HTTP {resp.status_code} from provider.", latency_ms=latency_ms)
            answer = parse_llm_json(extract_text(resp.json()))
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000.0, 1)
            return self._result(STATUS_ERROR, reason=f"{type(exc).__name__}: {exc}", latency_ms=latency_ms)

        return self._result(STATUS_OK, output_type="llm_generated", latency_ms=latency_ms, **answer)


class MultiLLMConsensusOrchestrator:
    """
    Runs the configured LLM engines and reports each result with its status.
    Name kept for compatibility; it no longer computes a consensus.
    """

    def __init__(self):
        self.engines: List[LLMEngine] = [
            LLMEngine("GPT-5.5", "OpenAI", "OPENAI_API_KEY",
                      _openai_compatible("https://api.openai.com/v1"), "OPENAI_MODEL", "gpt-5.5-preview"),
            LLMEngine("Claude 4 Opus", "Anthropic", "ANTHROPIC_API_KEY",
                      _anthropic, "ANTHROPIC_MODEL", "claude-4-opus-20260301"),
            LLMEngine("Gemini 2.5 Pro", "Google", "GEMINI_API_KEY",
                      _gemini, "GEMINI_MODEL", "gemini-2.5-pro"),
            LLMEngine("Llama 3.3 70B Instruct", "Meta", ""),
            LLMEngine("Qwen 3 72B", "Alibaba", ""),
            LLMEngine("DeepSeek-V3", "DeepSeek", "DEEPSEEK_API_KEY",
                      _openai_compatible("https://api.deepseek.com"), "DEEPSEEK_MODEL", "deepseek-chat"),
            LLMEngine("Mistral Large", "Mistral AI", "MISTRAL_API_KEY",
                      _openai_compatible("https://api.mistral.ai/v1"), "MISTRAL_MODEL", "mistral-large-latest"),
            LLMEngine("Command A", "Cohere", ""),
            LLMEngine("Falcon 180B", "TII", ""),
            LLMEngine("Phi-4", "Microsoft", ""),
        ]

    def find_engine(self, engine_id: str) -> Optional[LLMEngine]:
        target = re.sub(r"[^a-z0-9]", "", engine_id.lower())
        for eng in self.engines:
            if eng.engine_id == target:
                return eng
        return None

    def list_engines(self) -> List[Dict[str, Any]]:
        return [{
            "id": eng.engine_id,
            "name": eng.name,
            "developer": eng.developer,
            "implemented": eng.implemented,
            "api_key_configured": bool(eng.api_key),
            "model": eng.model or None,
            "model_id_verified": False,
        } for eng in self.engines]

    @staticmethod
    def summarise(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        ok = [r for r in results if r["status"] == STATUS_OK]
        return {
            "status": "available" if ok else UNAVAILABLE,
            "engines_queried": len(results),
            "engines_ok": len(ok),
            "phishing_verdicts_among_ok": sum(1 for r in ok if r["verdict"] == "PHISHING"),
            "legitimate_verdicts_among_ok": sum(1 for r in ok if r["verdict"] == "LEGITIMATE"),
            "aggregate": {"status": UNAVAILABLE, "reason": REASONS["llm_aggregate"]},
            "engine_results": results,
        }

    async def run_ensemble(self, url: str, dom_snippet: str = "",
                           lexical_features: Dict[str, Any] = None, gnn_stats: Dict[str, Any] = None) -> Dict[str, Any]:
        """Query every engine. lexical_features and gnn_stats are accepted for compatibility and ignored."""
        results = await asyncio.gather(*(eng.analyze(url, dom_snippet) for eng in self.engines))
        return self.summarise(list(results))

    async def run_single_engine(self, engine_id: str, url: str, dom_snippet: str = "",
                                lexical_features: Dict[str, Any] = None,
                                gnn_stats: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Returns None when the engine id is unknown."""
        eng = self.find_engine(engine_id)
        if eng is None:
            return None
        return await eng.analyze(url, dom_snippet)

    async def run_comparison(self, engine_ids: List[str], url: str, dom_snippet: str = "",
                             lexical_features: Dict[str, Any] = None,
                             gnn_stats: Dict[str, Any] = None) -> Dict[str, Any]:
        known = [self.find_engine(eid) for eid in engine_ids]
        unknown = [eid for eid, eng in zip(engine_ids, known) if eng is None]
        results = await asyncio.gather(*(eng.analyze(url, dom_snippet) for eng in known if eng is not None))
        summary = self.summarise(list(results))
        summary["target_url"] = url
        summary["unknown_engine_ids"] = unknown
        return summary


_orchestrator = None


def get_llm_orchestrator() -> MultiLLMConsensusOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiLLMConsensusOrchestrator()
    return _orchestrator


if __name__ == "__main__":
    report = asyncio.run(get_llm_orchestrator().run_ensemble("https://example.com", ""))
    for r in report["engine_results"]:
        print(f"{r['engine']:<24} {r['status']:<16} {r.get('reason', '')}")
