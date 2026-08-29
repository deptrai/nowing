"""Config domain: storage."""

from __future__ import annotations

import os

from app.config._helpers import (
    BASE_DIR,
)

# File storage (local filesystem by default; Azure Blob optional)
FILE_STORAGE_BACKEND = os.getenv("FILE_STORAGE_BACKEND", "local").strip().lower()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
FILE_STORAGE_LOCAL_PATH = os.getenv(
    "FILE_STORAGE_LOCAL_PATH", str(BASE_DIR / ".local_object_store")
)

# Daytona sandbox (code execution / filesystem sandbox)
DAYTONA_SANDBOX_ENABLED = (
    os.getenv("DAYTONA_SANDBOX_ENABLED", "FALSE").upper() == "TRUE"
)
DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "https://app.daytona.io/api")
DAYTONA_TARGET = os.getenv("DAYTONA_TARGET", "us")
DAYTONA_SNAPSHOT_ID = os.getenv("DAYTONA_SNAPSHOT_ID") or None
SANDBOX_FILES_DIR = os.getenv("SANDBOX_FILES_DIR", "sandbox_files")



__all__ = ['AZURE_STORAGE_CONNECTION_STRING', 'AZURE_STORAGE_CONTAINER', 'DAYTONA_API_KEY', 'DAYTONA_API_URL', 'DAYTONA_SANDBOX_ENABLED', 'DAYTONA_SNAPSHOT_ID', 'DAYTONA_TARGET', 'FILE_STORAGE_BACKEND', 'FILE_STORAGE_LOCAL_PATH', 'SANDBOX_FILES_DIR']
