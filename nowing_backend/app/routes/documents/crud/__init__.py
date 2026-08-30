"""Document CRUD, search, and status endpoints."""

from __future__ import annotations

from app.routes.documents.crud.list import *  # noqa: F403
from app.routes.documents.crud.misc import *  # noqa: F403
from app.routes.documents.crud.modify import *  # noqa: F403
from app.routes.documents.crud.read import *  # noqa: F403
from app.routes.documents.crud.router import router
from app.routes.documents.crud.search import *  # noqa: F403

__all__ = ["router"]
