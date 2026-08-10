"""fix client_id rls nullif for new_chat_threads and related

Revision ID: c826c8e6e149
Revises: da595e4c316a
Create Date: 2026-08-10 17:01:21.787352

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c826c8e6e149'
down_revision: str | None = 'da595e4c316a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Treat an empty-string client GUC as SQL NULL for RLS.

    ``set_request_tenant_context`` writes ``None`` as an empty string so a
    previous transaction-local value is cleared.  The existing Epic 18 chat
    RLS policies only checked ``current_setting(...) IS NULL``, which is
    never true after any ``set_config`` call.  Using ``NULLIF(..., '')``
    lets empty-string and unset GUCs both match rows whose ``client_id`` is
    NULL, which keeps legacy (pre-client) chat threads visible while still
    enforcing client isolation for scoped rows.
    """
    for table in (
        "new_chat_threads",
        "research_threads",
        "vertical_clients",
        "agent_configs",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_client_isolation_policy ON {table}")
        # chat/research tables have a creator column; let the owner see their
        # own rows even if the caller omits client_id in the request body.
        owner_clause = (
            " OR created_by_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_user_id', true), '')::uuid"
            if table in ("new_chat_threads", "research_threads")
            else ""
        )
        op.execute(
            f"""
            CREATE POLICY {table}_client_isolation_policy
            ON {table}
            FOR ALL
            TO PUBLIC
            USING (
                client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
                {owner_clause}
            )
            WITH CHECK (
                client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
                {owner_clause}
            )
        """
        )


def downgrade() -> None:
    """Restore the pre-NULLIF client isolation policies."""
    for table in (
        "new_chat_threads",
        "research_threads",
        "vertical_clients",
        "agent_configs",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_client_isolation_policy ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_client_isolation_policy
            ON {table}
            FOR ALL
            TO PUBLIC
            USING (
                client_id = current_setting('app.current_client_id', true)
                OR (
                    current_setting('app.current_client_id', true) IS NULL
                    AND client_id IS NULL
                )
            )
            WITH CHECK (
                client_id = current_setting('app.current_client_id', true)
                OR current_setting('app.current_client_id', true) IS NULL
            )
        """
        )
