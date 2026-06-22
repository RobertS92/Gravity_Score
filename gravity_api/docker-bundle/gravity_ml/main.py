#!/usr/bin/env python3
"""Run gravity-ml HTTP service."""

import os

import uvicorn

from gravity_ml.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
