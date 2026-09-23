"""Document CRUD, search, and status endpoints."""

from __future__ import annotations

from app.routes.documents.crud.list import *  # noqa: F403
from app.routes.documents.crud.misc import *  # noqa: F403
from app.routes.documents.crud.modify import *  # noqa: F403
from app.routes.documents.crud.router import router

# isort: skip_file
# `search` must be registered before `read`: it defines the literal
# `/documents/search` route, which `read`'s `/documents/{document_id}` path
# param would otherwise shadow (path ops match in registration order, so
# "search" would be parsed as a document_id). The isort:skip_file marker keeps
# ruff/isort from alphabetically re-ordering these imports and breaking that.
from app.routes.documents.crud.search import *  # noqa: F403  # isort: skip
from app.routes.documents.crud.read import *  # noqa: F403  # isort: skip

__all__ = ["router"]
