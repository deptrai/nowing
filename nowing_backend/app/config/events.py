"""Config domain: events."""

from __future__ import annotations

import os

# Capability run event bus backend. "memory" keeps events in-process (the
# default for single-process/test deployments); "redis" uses Redis pub/sub
# so multiple API replicas can tail the same run.
RUN_EVENT_BUS = os.getenv("RUN_EVENT_BUS", "memory").strip().lower()



__all__ = ['RUN_EVENT_BUS']
