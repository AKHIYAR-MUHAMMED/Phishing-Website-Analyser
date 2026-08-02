import os
import base64
from typing import Dict, Any, Optional
from vision_model import analyze_screenshot

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "screenshots")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ScreenshotService:
    """Microservice interface for screenshot capture, file upload processing, and visual AI analysis."""

    @staticmethod
    def capture(url: str, image_path: str = "") -> Dict[str, Any]:
        """Analyzes a website screenshot given a target URL or image path."""
        return analyze_screenshot(image_path, url)

    @staticmethod
    def analyze_upload(
        file_bytes: Optional[bytes] = None,
        filename: str = "uploaded_screenshot.png",
        target_url: str = "",
        base64_data: str = ""
    ) -> Dict[str, Any]:
        """
        Processes an uploaded screenshot image file or base64 data stream,
        saves a local copy for processing, and runs the 5-stage Visual AI pipeline.
        """
        saved_path = ""
        file_size_kb = 0.0

        if file_bytes:
            safe_filename = filename.replace("/", "_").replace("\\", "_")
            saved_path = os.path.join(UPLOAD_DIR, safe_filename)
            with open(saved_path, "wb") as f:
                f.write(file_bytes)
            file_size_kb = round(len(file_bytes) / 1024.0, 2)
        elif base64_data:
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]
            decoded = base64.b64decode(base64_data)
            saved_path = os.path.join(UPLOAD_DIR, "base64_upload.png")
            with open(saved_path, "wb") as f:
                f.write(decoded)
            file_size_kb = round(len(decoded) / 1024.0, 2)

        # Execute Visual Transformer & Hybrid Vision Suite Analysis
        analysis = analyze_screenshot(saved_path, target_url or "Uploaded Screenshot")
        
        analysis["file_info"] = {
            "filename": filename,
            "saved_path": saved_path,
            "file_size_kb": file_size_kb,
            "source": "FILE_UPLOAD" if file_bytes else ("BASE64_DATA" if base64_data else "LIVE_CAPTURE")
        }

        return analysis

