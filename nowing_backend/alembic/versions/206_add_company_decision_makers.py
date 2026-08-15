"""add company decision makers and linkedin tables (Story 21.9)

Revision ID: 206
Revises: 205
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "206"
down_revision: str | None = "205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exec_statements(*statements: str) -> None:
    for stmt in statements:
        op.execute(text(stmt))


def upgrade() -> None:
    _exec_statements(
        """
        CREATE TABLE IF NOT EXISTS linkedin_companies (
            id BIGSERIAL PRIMARY KEY,
            company_slug VARCHAR(255) NOT NULL UNIQUE,
            company_name TEXT NOT NULL,
            website TEXT,
            industry VARCHAR(255),
            headcount_range VARCHAR(50),
            headquarters VARCHAR(255),
            active_jobs_count INT DEFAULT 0,
            decision_makers JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS linkedin_jobs (
            id BIGSERIAL PRIMARY KEY,
            job_id VARCHAR(100) NOT NULL UNIQUE,
            company_id BIGINT REFERENCES linkedin_companies(id) ON DELETE SET NULL,
            company_name VARCHAR(255) NOT NULL,
            title TEXT NOT NULL,
            location VARCHAR(255),
            workplace_type VARCHAR(50),
            seniority_level VARCHAR(50),
            employment_type VARCHAR(50),
            description_text TEXT,
            skills TEXT[],
            posted_at TIMESTAMPTZ,
            raw_entities JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS company_decision_makers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id BIGINT REFERENCES linkedin_companies(id) ON DELETE CASCADE,
            company_name VARCHAR(255) NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            title VARCHAR(255),
            department VARCHAR(100),
            linkedin_url TEXT,
            linkedin_slug VARCHAR(255) NOT NULL,
            email_prediction VARCHAR(255),
            confidence_score FLOAT NOT NULL DEFAULT 0.0,
            verified_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_company_executive UNIQUE (company_id, linkedin_slug)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_executives_company_title ON company_decision_makers(company_name, title);",
        "CREATE INDEX IF NOT EXISTS idx_executives_slug ON company_decision_makers(linkedin_slug);",
        "CREATE INDEX IF NOT EXISTS idx_linkedin_jobs_company_id ON linkedin_jobs(company_id);",
    )


def downgrade() -> None:
    _exec_statements(
        "DROP TABLE IF EXISTS company_decision_makers CASCADE;",
        "DROP TABLE IF EXISTS linkedin_jobs CASCADE;",
        "DROP TABLE IF EXISTS linkedin_companies CASCADE;",
    )
