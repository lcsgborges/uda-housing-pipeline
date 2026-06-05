from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentStatus(StrEnum):
    discovered = "discovered"
    downloaded = "downloaded"
    classifying = "classifying"
    classified_useful = "classified_useful"
    processing = "processing"
    processed = "processed"
    failed = "failed"
    ignored_not_relevant = "ignored_not_relevant"
    ignored_duplicate = "ignored_duplicate"
    needs_ocr = "needs_ocr"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    original_url: Mapped[str] = mapped_column(String(700), nullable=False)
    local_path: Mapped[str | None] = mapped_column(String(700), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    classification_is_useful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detected_domains: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    extraction_strategy: Mapped[str | None] = mapped_column(String(40), nullable=True)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.discovered, nullable=False
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    company = relationship("Company", back_populates="documents")
    metrics = relationship("Metric", back_populates="document", cascade="all, delete-orphan")
    insights = relationship(
        "DocumentInsight",
        back_populates="document",
        cascade="all, delete-orphan",
    )
