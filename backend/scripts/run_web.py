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

if __name__ == "__main__":
    print("=" * 50)
    print("  Datalogger Local Web UI")
    print("  http://localhost:5000")
    print("=" * 50)
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=5000,
        reload=False,
        log_level="info"
    )
