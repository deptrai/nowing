"""``masothue`` capability namespace."""

from __future__ import annotations

# Import the scrape capability so it registers at app startup.
from .scrape import definition as _definition  # noqa: F401
