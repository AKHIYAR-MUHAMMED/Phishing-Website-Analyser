"""
PyTorch Vision Transformer (ViT), Phishpedia, VisualPhishNet & Perceptual Hashing Microservices.
Exposes endpoints for MDPI 2026 visual detection & target recognition algorithms (Jarczewski et al.).
"""

from typing import Dict, Any
from vision_model import analyze_screenshot, get_vit_model, get_hybrid_visual_detector, PerceptualHashEngine, PhishpediaEngine, VisualPhishNetEngine


class ViTService:
    @staticmethod
    def predict(url: str, image_path: str = "") -> Dict[str, Any]:
        res = analyze_screenshot(image_path, url)
        return {
            "model_name": "PyTorch Vision Transformer (ViT) & MDPI 2026 Visual Suite",
            "vit_threat_score": res["vit_threat_score"],
            "detected_logo": res["detected_logo"],
            "form_layout_verdict": res["form_layout_verdict"],
            "ocr_extracted_text": res["ocr_extracted_text"],
            "mdpi_2026_visual_suite": res["mdpi_2026_visual_suite"]
        }

    @staticmethod
    def predict_phash(url: str) -> Dict[str, Any]:
        engine = PerceptualHashEngine()
        return engine.evaluate(url)

    @staticmethod
    def predict_phishpedia(url: str) -> Dict[str, Any]:
        engine = PhishpediaEngine()
        return engine.evaluate(url)

    @staticmethod
    def predict_visualphishnet(url: str) -> Dict[str, Any]:
        engine = VisualPhishNetEngine()
        return engine.evaluate(url)

    @staticmethod
    def predict_hybrid_visual(url: str) -> Dict[str, Any]:
        detector = get_hybrid_visual_detector()
        return detector.analyze_full_visual_suite(url)
