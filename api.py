"""
PhishGuard API gateway.

Phase 0 honesty pass:
- /api/v1/scan (alias /api/v1/detect) runs the scan pipeline ONCE and returns genuine
  observations plus the status of every modality. It returns no verdict until a trained
  fusion model exists. Latency is measured.
- Endpoints whose component was simulated respond with HTTP 501 and an explicit reason.
- Status endpoints (metrics, history, datasets, system) report "not_evaluated" or
  "unavailable" instead of hard-coded numbers.
"""

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services import (
    GNNService,
    LLMService,
    FusionService,
    DatasetService,
    DashboardService,
)
from component_status import NOT_EVALUATED, REASONS, unavailable
from database import init_db

app = FastAPI(
    title="PhishGuard API",
    description="Phishing website analysis API. Components that are not yet genuinely implemented "
                "report an explicit unavailable status.",
    version="0.1.0-honesty-pass",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")
if os.path.exists(DASHBOARD_DIR):
    app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@app.on_event("startup")
def on_startup():
    init_db()


# Request models
class ScanRequest(BaseModel):
    url: str
    html_content: Optional[str] = ""


class BatchScanRequest(BaseModel):
    urls: List[str]


class LoginRequest(BaseModel):
    username: str
    password: str


class CompareLLMRequest(BaseModel):
    engine_ids: List[str]
    url: str
    dom_snippet: Optional[str] = ""


class ImageRequest(BaseModel):
    url: Optional[str] = ""
    image_path: Optional[str] = ""
    base64_data: Optional[str] = ""


def not_available(component: str) -> JSONResponse:
    """HTTP 501 for endpoints whose component was simulated and is now disabled."""
    return JSONResponse(status_code=501, content=unavailable(component))


def require_url(url: str) -> str:
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="Target URL cannot be empty.")
    return url.strip()


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_path = os.path.join(DASHBOARD_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>PhishGuard API</h1><p>See <a href='/docs'>/docs</a>.</p>")


@app.get("/demo", response_class=HTMLResponse)
async def serve_honest_demo():
    """The new, honest demo dashboard (calls /api/v2/analyze only) — separate from the legacy
    dashboard at "/", which is being replaced (see README's rebuild notice)."""
    demo_path = os.path.join(DASHBOARD_DIR, "demo.html")
    with open(demo_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# --- Scan pipeline ---

@app.post("/api/v1/scan")
@app.post("/api/v1/detect")
@app.post("/models/fusion/predict")
async def scan_endpoint(req: ScanRequest):
    """Runs the scan pipeline once. No verdict is returned until a trained fusion model exists."""
    return await FusionService.predict(require_url(req.url), req.html_content or "")


@app.post("/api/v1/batch-scan")
async def batch_scan_endpoint(req: BatchScanRequest):
    urls = [u.strip() for u in req.urls if u and u.strip()][:10]
    if not urls:
        raise HTTPException(status_code=400, detail="URL list cannot be empty.")
    results = []
    for url in urls:
        report = await FusionService.predict(url, "")
        results.append({
            "url": url,
            "verdict": report["verdict"],
            "phishing_probability": report["phishing_probability"],
            "decision": report["decision"],
            "processing_latency_ms": report["processing_latency_ms"],
        })
    return {"total_scanned": len(results), "batch_results": results}


# --- Individual components ---

@app.post("/models/gnn/predict")
async def gnn_model_endpoint(req: ScanRequest):
    """Returns DOM graph statistics; the GNN model output itself is unavailable."""
    return GNNService.predict(req.html_content or "", require_url(req.url))


@app.get("/models/llm/list")
async def list_llm_models_endpoint():
    engines = LLMService.list_engines()
    return {"engines": engines, "listed_engines": len(engines),
            "implemented_engines": sum(1 for e in engines if e["implemented"])}


@app.post("/models/llm/predict")
async def llm_model_endpoint(req: ScanRequest):
    return await LLMService.predict(require_url(req.url), (req.html_content or "")[:1000])


@app.post("/models/llm/compare")
async def compare_llm_models_endpoint(req: CompareLLMRequest):
    return await LLMService.compare_engines(req.engine_ids, require_url(req.url), (req.dom_snippet or "")[:1000])


@app.post("/models/llm/{engine_id}/predict")
async def single_llm_model_endpoint(engine_id: str, req: ScanRequest):
    result = await LLMService.predict_engine(engine_id, require_url(req.url), (req.html_content or "")[:1000])
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown LLM engine id: {engine_id}")
    return result


# Disabled (previously simulated) components -> HTTP 501 with an explicit reason.

@app.post("/models/vit/predict")
@app.post("/models/phishpedia/predict")
@app.post("/models/visualphishnet/predict")
@app.post("/models/phash/predict")
@app.post("/models/visual-hybrid/predict")
@app.post("/api/v1/screenshot/analyze")
async def visual_model_endpoint(req: ImageRequest):
    return not_available("visual")


@app.post("/api/v1/screenshot/upload")
async def upload_screenshot_endpoint(file: UploadFile = File(...), target_url: Optional[str] = Form(None)):
    """Upload is not stored or analysed: no visual model exists."""
    return not_available("visual")


@app.post("/models/bert/predict")
async def bert_model_endpoint(req: ScanRequest):
    return not_available("bert")


@app.post("/models/ensemble/predict")
@app.post("/models/rf/predict")
@app.post("/models/catboost/predict")
async def classical_model_endpoint(req: ScanRequest):
    return not_available("classical_ml")


@app.post("/models/autoencoder/predict")
async def autoencoder_endpoint(req: ScanRequest):
    return not_available("anomaly")


@app.post("/models/xai/predict")
async def xai_model_endpoint(req: ScanRequest):
    return not_available("explanation")


@app.get("/api/v1/eer-optimize")
@app.post("/api/v1/eer-optimize")
@app.get("/api/v1/benchmark-comparison")
async def benchmark_endpoint():
    return not_available("benchmark")


@app.get("/api/v1/screenshot-datasets")
@app.post("/api/v1/screenshot-datasets/connect")
@app.get("/api/v1/datasets/fetch-external")
@app.post("/api/v1/datasets/fetch-external")
async def screenshot_datasets_endpoint():
    return not_available("screenshot_datasets")


@app.get("/api/v1/datasets/export")
@app.post("/api/v1/datasets/export")
async def export_dataset_endpoint():
    return not_available("dataset")


@app.get("/api/v1/datasets/validate")
async def validate_dataset_endpoint():
    """Genuine file checks on the committed (synthetic) CSV."""
    return DatasetService.validate_dataset()


# --- Status endpoints ---

@app.get("/dashboard/system")
@app.get("/api/v1/dashboard")
@app.get("/dashboard/models")
@app.get("/api/v1/model_info")
async def get_component_status():
    return DashboardService.get_telemetry()


@app.get("/dashboard/datasets")
@app.get("/api/v1/dataset_stats")
@app.get("/api/v1/dataset-stats")
async def get_dashboard_datasets():
    return DatasetService.get_dataset_statistics()


@app.get("/dashboard/history")
@app.get("/api/v1/history")
async def get_dashboard_history():
    return unavailable("scan_history")


@app.get("/api/v1/metrics")
async def get_metrics():
    return {"status": NOT_EVALUATED, "reason": REASONS["evaluation"], "metrics": None}


@app.get("/api/v1/health")
async def health_check():
    """Reports only that the API process is running."""
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
async def login_user(req: LoginRequest):
    return not_available("auth")


# --- Demo pipeline (project review): real crawl -> real features -> real DOM graph ->
# real GNN forward pass (retrained on the actual small Phase 3 dataset, not the synthetic
# template) -> disclosed rule-based semantic heuristic (no LLM key configured) -> honest
# fusion. See analysis_pipeline.py for the full chain and its disclosed limitations. ---

class AnalyzeRequest(BaseModel):
    url: str


@app.post("/api/v2/analyze")
async def analyze_url_endpoint(req: AnalyzeRequest):
    from analysis_pipeline import analyze_url
    return await analyze_url(req.url)
