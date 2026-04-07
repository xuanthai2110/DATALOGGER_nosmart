#!/usr/bin/env python3
"""
scripts/run_web.py — Khởi động Local Web UI cho cấu hình Datalogger
Truy cập: http://<raspberry-pi-ip>:8080
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import uvicorn
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from backend.core import settings

if __name__ == "__main__":
    print("=" * 50)
    print("  Datalogger Local Web UI")
    print(f"  http://{settings.WEB_HOST}:{settings.WEB_PORT}")
    print("=" * 50)
    uvicorn.run(
        "backend.app:app",
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        reload=False,
        log_level="info"
    )
