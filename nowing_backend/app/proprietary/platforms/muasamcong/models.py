"""Database models for Public Procurement Tenders (Story 16.5 / AD-PROC-2, AD-PROC-3, AD-PROC-6)."""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin


class ProcurementTender(BaseModel, TimestampMixin):
    """Stores public procurement tenders (TBMT) ingested from muasamcong.mpi.gov.vn."""

    __tablename__ = "procurement_tenders"

    # Composite uniqueness via (bid_no, bid_turn_no) as per AD-PROC-6
    bid_no = Column(String(100), nullable=False, index=True)
    bid_turn_no = Column(String(10), nullable=False, default="00", server_default="00")

    project_name = Column(Text, nullable=False)
    procuring_entity = Column(Text, nullable=True)
    investor = Column(Text, nullable=True)
    field = Column(String(100), nullable=True, index=True)
    bid_type = Column(String(50), nullable=True)
    funding_source = Column(Text, nullable=True)

    bid_price = Column(Numeric(18, 2), nullable=True)
    bid_open_date = Column(DateTime(timezone=True), nullable=True)
    bid_closing_at = Column(DateTime(timezone=True), nullable=True, index=True)
    location = Column(String(255), nullable=True)

    dossier_url = Column(Text, nullable=True)
    raw_specs = Column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    summary_md = Column(Text, nullable=True)
    embedding = Column(Vector(1536), nullable=True)

    status = Column(String(50), nullable=False, default="active", server_default="active")

    chunks = relationship(
        "ProcurementTenderChunk",
        back_populates="tender",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("bid_no", "bid_turn_no", name="uq_procurement_tender"),
        Index("idx_procurement_bid_closing", "bid_closing_at"),
        Index("idx_procurement_field", "field"),
        Index(
            "idx_procurement_tender_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class ProcurementTenderChunk(BaseModel, TimestampMixin):
    """Vectorized text chunks from E-HSMT dossiers for semantic tender search (AD-PROC-3)."""

    __tablename__ = "procurement_tender_chunks"

    tender_id = Column(
        Integer,
        ForeignKey("procurement_tenders.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    section_title = Column(String(255), nullable=True)
    embedding = Column(Vector(1536), nullable=True)

    tender = relationship("ProcurementTender", back_populates="chunks")

    __table_args__ = (
        Index("idx_procurement_tender_chunk_order", "tender_id", "chunk_index"),
        Index(
            "idx_procurement_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
