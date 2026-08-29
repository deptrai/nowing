"""Application configuration package."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Get the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env_file = BASE_DIR / ".env"
load_dotenv(env_file)

os.environ.setdefault("OR_APP_NAME", "Nowing")
os.environ.setdefault("OR_SITE_URL", "https://nowing.com")

logger = logging.getLogger(__name__)

# Startup helpers are still accessed directly from the package namespace.
from app.config._helpers import (  # noqa: E402
    initialize_image_gen_router,
    initialize_llm_router,
    initialize_openrouter_integration,
    initialize_pricing_registration,
    load_global_llm_configs,
    load_openrouter_integration_settings,
    materialize_global_configs,
    refresh_global_model_catalog,
)

# Domain modules populate this package namespace before we build Config.
# Import order matters: later modules may override earlier ones for legacy
# constants defined in more than one place (e.g. ``FILE_STORAGE_LOCAL_PATH``
# is canonical in ``web_builder``).
from app.config.agents import *  # noqa: E402, F403
from app.config.auth import *  # noqa: E402, F403
from app.config.billing import *  # noqa: E402, F403
from app.config.celery import *  # noqa: E402, F403
from app.config.chainlens import *  # noqa: E402, F403
from app.config.connectors import *  # noqa: E402, F403
from app.config.core import *  # noqa: E402, F403
from app.config.database import *  # noqa: E402, F403
from app.config.dsh import *  # noqa: E402, F403
from app.config.entities import *  # noqa: E402, F403
from app.config.etl import *  # noqa: E402, F403
from app.config.events import *  # noqa: E402, F403
from app.config.gateway import *  # noqa: E402, F403
from app.config.llm import *  # noqa: E402, F403
from app.config.media import *  # noqa: E402, F403
from app.config.memory import *  # noqa: E402, F403
from app.config.oauth import *  # noqa: E402, F403
from app.config.quota import *  # noqa: E402, F403
from app.config.research import *  # noqa: E402, F403
from app.config.scraper import *  # noqa: E402, F403
from app.config.storage import *  # noqa: E402, F403
from app.config.urls import *  # noqa: E402, F403
from app.config.web_builder import *  # noqa: E402, F403


class Config:
    """Backward-compatible config namespace."""

    def __getattr__(self, name: str):
        """Resolve attribute from the package namespace."""
        try:
            return getattr(sys.modules[__name__], name)
        except AttributeError:
            raise AttributeError(f"Config has no attribute {name!r}") from None

    @classmethod
    def is_self_hosted(cls) -> bool:
        """Check if running in self-hosted mode."""
        return cls.DEPLOYMENT_MODE == "self-hosted"

    @classmethod
    def is_cloud(cls) -> bool:
        """Check if running in cloud mode."""
        return cls.DEPLOYMENT_MODE == "cloud"

    @classmethod
    def get_settings(cls):
        """Get all settings as a dictionary."""
        module = sys.modules[__name__]
        return {
            key: value
            for key, value in module.__dict__.items()
            if not key.startswith("_") and not callable(value)
        }


# Build the class namespace so ``Config.REDIS_URL`` works the same as
# ``config.REDIS_URL``.  This keeps module-level constants as the source of
# truth while preserving the original class-based API.
_module = sys.modules[__name__]
for _name in list(_module.__dict__.keys()):
    _value = _module.__dict__[_name]
    if (
        not _name.startswith("_")
        and not callable(_value)
        and _name not in {"Config", "config", "logger", "os", "sys", "Path", "load_dotenv"}
    ):
        setattr(Config, _name, _value)

# Create a config instance
config = Config()

HOSTING_BASE_DOMAIN = config.HOSTING_BASE_DOMAIN
CNAME_INGRESS_HOST = config.CNAME_INGRESS_HOST
FILE_STORAGE_LOCAL_PATH = config.FILE_STORAGE_LOCAL_PATH

__all__ = [
    "BASE_DIR",
    "CNAME_INGRESS_HOST",
    "FILE_STORAGE_LOCAL_PATH",
    "HOSTING_BASE_DOMAIN",
    "Config",
    "config",
    "initialize_image_gen_router",
    "initialize_llm_router",
    "initialize_openrouter_integration",
    "initialize_pricing_registration",
    "load_global_llm_configs",
    "load_openrouter_integration_settings",
    "materialize_global_configs",
    "refresh_global_model_catalog",
]
