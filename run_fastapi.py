#!/usr/bin/env python3
"""
Production-ready FastAPI server runner with performance optimizations
"""

import uvicorn
import os

if __name__ == "__main__":
    # Production configuration
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    workers = int(os.getenv("WORKERS", 1))
    
    uvicorn.run(
        "fastapi_app:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,  # Set to True for development
        access_log=True,
        log_level="info",
        loop="asyncio"
    )